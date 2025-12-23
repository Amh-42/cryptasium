"""
Main Flask application for Cryptasium
"""
from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
from datetime import datetime
import os
import markdown

from config import config
from models import (
    db, BlogPost, YouTubeVideo, Podcast, Short, CommunityPost, TopicIdea,
    GamificationStats, get_video_content_type, get_rank_for_stats,
    DailyXPLog, WeeklyProgress, MonthlyProgress, YearlyMilestones, ArchitectRankProgress,
    SystemSettings, Rank, ContentPointValue, DailyTask, WeeklyRequirement,
    get_content_points, get_daily_xp_goal, get_perfect_week_bonus, get_points_name
)
import youtube_service




def create_app(config_name=None):
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Load configuration
    config_name = config_name or os.environ.get('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])
    
    # Initialize database
    db.init_app(app)
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    # Register markdown filter
    @app.template_filter('markdown')
    def markdown_filter(text):
        """Convert markdown to HTML with Obsidian-style support"""
        if not text:
            return ''
        try:
            import re
            # Convert Obsidian-style wikilinks [[link]] to markdown links
            text = re.sub(r'\[\[([^\]]+)\]\]', r'[\1](\1)', text)
            # Convert ![[image]] to ![image](image)
            text = re.sub(r'!\[\[([^\]]+)\]\]', r'![\1](\1)', text)
            # Convert ==highlight== to <mark>highlight</mark>
            text = re.sub(r'==([^=]+)==', r'<mark>\1</mark>', text)
            
            # Create markdown instance with extensions
            extensions = ['fenced_code', 'tables', 'nl2br', 'sane_lists']
            # Only add codehilite if Pygments is available
            try:
                import pygments
                extensions.append('codehilite')
            except ImportError:
                pass
            
            md = markdown.Markdown(extensions=extensions)
            result = md.convert(str(text))
            md.reset()  # Reset for next use
            return result
        except Exception as e:
            # If markdown fails, return the text as-is (escaped)
            import html
            print(f"Markdown filter error: {str(e)}")
            return html.escape(str(text))
    
    # ========== HELPER FUNCTIONS ==========
    
    # Track last sync time to avoid excessive API calls
    app.config['_last_sync_time'] = None
    app.config['_sync_interval_hours'] = 1  # Sync at most once per hour
    
    def auto_sync_youtube():
        """
        Auto-sync YouTube videos and shorts.
        Only syncs if more than _sync_interval_hours have passed since last sync.
        Returns a message if new content was added, None otherwise.
        """
        # Check if we should sync
        now = datetime.utcnow()
        last_sync = app.config.get('_last_sync_time')
        interval = app.config.get('_sync_interval_hours', 1)
        
        if last_sync:
            hours_since_sync = (now - last_sync).total_seconds() / 3600
            if hours_since_sync < interval:
                return None  # Too soon to sync again
        
        try:
            videos, shorts, error = youtube_service.fetch_channel_videos(50)
            
            if error:
                return None  # Don't report errors during auto-sync
            
            videos_added = 0
            shorts_added = 0
            
            # Add new videos and update existing ones with latest stats
            for v in videos:
                existing = YouTubeVideo.query.filter_by(video_id=v['video_id']).first()
                duration_seconds = v.get('duration_seconds', 0)
                content_type = get_video_content_type(duration_seconds)
                
                if existing:
                    # Update existing video stats
                    existing.views = v.get('view_count', 0)
                    existing.title = v['title']
                    existing.thumbnail_url = v['thumbnail_url']
                    existing.duration = v['duration']
                    existing.duration_seconds = duration_seconds
                    existing.content_type = content_type
                else:
                    video = YouTubeVideo(
                        title=v['title'],
                        description=v['description'][:500] if v['description'] else '',
                        video_id=v['video_id'],
                        thumbnail_url=v['thumbnail_url'],
                        duration=v['duration'],
                        duration_seconds=duration_seconds,
                        content_type=content_type,
                        views=v.get('view_count', 0),
                        published=True,
                        created_at=v['published_at']
                    )
                    db.session.add(video)
                    videos_added += 1
            
            # Add new shorts and update existing ones
            for s in shorts:
                existing = Short.query.filter_by(video_id=s['video_id']).first()
                if existing:
                    # Update existing short stats
                    existing.views = s.get('view_count', 0)
                    existing.title = s['title']
                    existing.thumbnail_url = s['thumbnail_url']
                    existing.duration = s['duration']
                else:
                    short = Short(
                        title=s['title'],
                        description=s['description'][:500] if s['description'] else '',
                        video_id=s['video_id'],
                        thumbnail_url=s['thumbnail_url'],
                        duration=s['duration'],
                        views=s.get('view_count', 0),
                        published=True,
                        created_at=s['published_at']
                    )
                    db.session.add(short)
                    shorts_added += 1
            
            if videos_added or shorts_added:
                db.session.commit()
                app.config['_last_sync_time'] = now
                return f"Auto-synced: +{videos_added} videos, +{shorts_added} shorts"
            
            app.config['_last_sync_time'] = now
            return None
            
        except Exception:
            return None  # Silently fail during auto-sync
    
    def calculate_gamification_stats():
        """
        Calculate and update gamification statistics based on all content.
        Returns the updated GamificationStats object.
        """
        # Get or create the stats record (we use a single row for global stats)
        stats = GamificationStats.query.first()
        if not stats:
            stats = GamificationStats()
            db.session.add(stats)
        
        # Get content point values from database
        content_points_db = get_content_points()
        
        # Count and calculate points for each content type
        
        # 1. Blog posts
        blog_count = BlogPost.query.filter_by(published=True).count()
        blog_points = blog_count * content_points_db.get('blog', 50)
        
        # 2. Shorts (from Short model)
        shorts_count = Short.query.filter_by(published=True).count()
        shorts_points = shorts_count * content_points_db.get('shorts', 100)
        
        # 3. Podcasts
        podcast_count = Podcast.query.filter_by(published=True).count()
        podcast_points = podcast_count * content_points_db.get('podcast', 400)
        
        # 4. YouTube Videos (categorized by duration)
        videos = YouTubeVideo.query.filter_by(published=True).all()
        
        short_longs_count = 0
        mid_longs_count = 0
        longs_count = 0
        
        for video in videos:
            # Determine content type based on duration_seconds
            duration_sec = video.duration_seconds or 0
            
            # If duration_seconds is 0, try to parse from duration string
            if duration_sec == 0 and video.duration:
                parts = video.duration.split(':')
                if len(parts) == 3:  # H:MM:SS
                    duration_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                elif len(parts) == 2:  # M:SS
                    duration_sec = int(parts[0]) * 60 + int(parts[1])
                
                # Update the video record with duration_seconds
                video.duration_seconds = duration_sec
            
            # Categorize video
            content_type = get_video_content_type(duration_sec)
            video.content_type = content_type
            
            if content_type == 'short_longs':
                short_longs_count += 1
            elif content_type == 'mid_longs':
                mid_longs_count += 1
            elif content_type == 'longs':
                longs_count += 1
        
        short_longs_points = short_longs_count * content_points_db.get('short_longs', 200)
        mid_longs_points = mid_longs_count * content_points_db.get('mid_longs', 800)
        longs_points = longs_count * content_points_db.get('longs', 1000)
        
        # Calculate totals
        content_points_total = (blog_points + shorts_points + short_longs_points + 
                         podcast_points + mid_longs_points + longs_points)
        total_content = (blog_count + shorts_count + short_longs_count + 
                        podcast_count + mid_longs_count + longs_count)
        
        # Calculate total views
        total_video_views = db.session.query(db.func.sum(YouTubeVideo.views)).scalar() or 0
        total_shorts_views = db.session.query(db.func.sum(Short.views)).scalar() or 0
        total_blog_views = db.session.query(db.func.sum(BlogPost.views)).scalar() or 0
        total_views = total_video_views + total_shorts_views + total_blog_views
        
        # Calculate subscriber and view points
        subscriber_count = stats.subscriber_count or 0
        subscriber_points = int(subscriber_count * content_points_db.get('subscriber', 20))
        views_points = int(total_views * content_points_db.get('view', 0.5))
        
        # Total points includes content + subscriber + view points + daily XP
        # Preserve existing daily_xp_points from daily tasks
        daily_xp_points = stats.daily_xp_points or 0
        total_points = content_points_total + subscriber_points + views_points + daily_xp_points
        
        # Update stats
        stats.blog_count = blog_count
        stats.blog_points = blog_points
        stats.shorts_count = shorts_count
        stats.shorts_points = shorts_points
        stats.short_longs_count = short_longs_count
        stats.short_longs_points = short_longs_points
        stats.podcast_count = podcast_count
        stats.podcast_points = podcast_points
        stats.mid_longs_count = mid_longs_count
        stats.mid_longs_points = mid_longs_points
        stats.longs_count = longs_count
        stats.longs_points = longs_points
        stats.subscriber_points = subscriber_points
        stats.views_points = views_points
        
        stats.total_points = total_points
        stats.total_content_count = total_content
        stats.total_views = total_views
        stats.updated_at = datetime.utcnow()
        
        # Calculate and update rank
        stats.calculate_rank()
        
        db.session.commit()
        return stats
    
    def sync_channel_stats():
        """Sync subscriber count and channel stats from YouTube API"""
        try:
            channel_data, error = youtube_service.fetch_channel_statistics()
            if error:
                return None, error
            
            stats = GamificationStats.query.first()
            if not stats:
                stats = GamificationStats()
                db.session.add(stats)
            
            stats.subscriber_count = channel_data['subscriber_count']
            stats.total_channel_views = channel_data['view_count']
            stats.last_sync_at = datetime.utcnow()
            
            # Recalculate rank with new subscriber count
            stats.calculate_rank()
            
            db.session.commit()
            return stats, None
        except Exception as e:
            return None, str(e)
    
    def admin_required(f):
        """Decorator to require admin authentication"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('admin_logged_in'):
                flash('Please log in to access admin panel.', 'error')
                return redirect(url_for('admin_login'))
            return f(*args, **kwargs)
        return decorated_function
    
    # ========== PUBLIC ROUTES ==========
    
    @app.route('/offline')
    def offline():
        """Offline page for PWA"""
        return render_template('offline.html')
    
    @app.route('/')
    def index():
        """Homepage"""
        # Get latest content for homepage
        latest_blog = BlogPost.query.filter_by(published=True).order_by(BlogPost.created_at.desc()).first()
        latest_videos = YouTubeVideo.query.filter_by(published=True).order_by(YouTubeVideo.created_at.desc()).limit(3).all()
        latest_shorts = Short.query.filter_by(published=True).order_by(Short.created_at.desc()).limit(3).all()
        
        return render_template('index.html', 
                             latest_blog=latest_blog,
                             latest_videos=latest_videos,
                             latest_shorts=latest_shorts)
    
    @app.route('/about')
    def about():
        """About page"""
        return render_template('about.html')
    
    @app.route('/submit-idea', methods=['GET', 'POST'])
    def submit_idea():
        """Submit topic idea page"""
        if request.method == 'POST':
            topic = request.form.get('topic', '').strip()
            description = request.form.get('description', '').strip()
            email = request.form.get('email', '').strip()
            name = request.form.get('name', '').strip()
            
            if not topic or not description:
                flash('Please fill in both topic and description fields.', 'error')
                return render_template('submit_idea.html')
            
            try:
                idea = TopicIdea(
                    topic=topic,
                    description=description,
                    email=email if email else None,
                    name=name if name else None
                )
                db.session.add(idea)
                db.session.commit()
                flash('Thank you! Your idea has been submitted successfully. We\'ll review it soon.', 'success')
                return redirect(url_for('submit_idea'))
            except Exception as e:
                db.session.rollback()
                flash('An error occurred. Please try again.', 'error')
                return render_template('submit_idea.html')
        
        return render_template('submit_idea.html')
    
    @app.route('/blog')
    def blog_list():
        """Blog listing page"""
        page = request.args.get('page', 1, type=int)
        posts = BlogPost.query.filter_by(published=True)\
            .order_by(BlogPost.created_at.desc())\
            .paginate(page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
        
        return render_template('blog.html', posts=posts)
    
    @app.route('/blog/<slug>')
    def blog_detail(slug):
        """Blog post detail page"""
        # Try to get the post - check both published and unpublished for debugging
        post = BlogPost.query.filter_by(slug=slug).first()
        
        if not post:
            from flask import abort
            abort(404)
        
        # Only show published posts to public, but allow viewing if exists
        if not post.published:
            from flask import abort
            abort(404)
        
        # Increment views
        if post.views is None:
            post.views = 0
        post.views += 1
        db.session.commit()
        
        return render_template('post_detail.html', post=post)
    
    @app.route('/youtube')
    def youtube_list():
        """YouTube videos listing page"""
        page = request.args.get('page', 1, type=int)
        videos = YouTubeVideo.query.filter_by(published=True)\
            .order_by(YouTubeVideo.created_at.desc())\
            .paginate(page=page, per_page=app.config['VIDEOS_PER_PAGE'], error_out=False)
        
        return render_template('youtube.html', videos=videos)
    
    @app.route('/podcast')
    def podcast_list():
        """Podcast episodes listing page"""
        page = request.args.get('page', 1, type=int)
        podcasts = Podcast.query.filter_by(published=True)\
            .order_by(Podcast.created_at.desc())\
            .paginate(page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
        
        return render_template('podcast.html', podcasts=podcasts)
    
    @app.route('/shorts')
    def shorts_list():
        """Shorts listing page"""
        page = request.args.get('page', 1, type=int)
        shorts = Short.query.filter_by(published=True)\
            .order_by(Short.created_at.desc())\
            .paginate(page=page, per_page=app.config['SHORTS_PER_PAGE'], error_out=False)
        
        return render_template('shorts.html', shorts=shorts)
    
    @app.route('/community')
    def community_list():
        """Community posts listing page"""
        page = request.args.get('page', 1, type=int)
        posts = CommunityPost.query.filter_by(published=True)\
            .order_by(CommunityPost.created_at.desc())\
            .paginate(page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
        
        return render_template('community.html', posts=posts)
    
    # ========== ADMIN ROUTES ==========
    
    @app.route('/admin/login', methods=['GET', 'POST'])
    def admin_login():
        """Admin login page"""
        # Redirect to dashboard if already logged in
        if session.get('admin_logged_in'):
            return redirect(url_for('admin_dashboard'))
        
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            if username == app.config['ADMIN_USERNAME'] and \
               password == app.config['ADMIN_PASSWORD']:
                session['admin_logged_in'] = True
                flash('Logged in successfully!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid credentials.', 'error')
        
        return render_template('admin/login.html')
    
    @app.route('/admin/logout')
    def admin_logout():
        """Admin logout"""
        session.pop('admin_logged_in', None)
        flash('Logged out successfully.', 'success')
        return redirect(url_for('index'))
    
    @app.route('/admin')
    @admin_required
    def admin_dashboard():
        """Admin dashboard"""
        # Auto-sync YouTube content (checks for new videos)
        sync_message = None
        try:
            sync_result = auto_sync_youtube()
            if sync_result:
                sync_message = sync_result
        except Exception as e:
            sync_message = f"Auto-sync error: {str(e)}"
        
        # Calculate total views for YouTube content
        total_video_views = db.session.query(db.func.sum(YouTubeVideo.views)).scalar() or 0
        total_shorts_views = db.session.query(db.func.sum(Short.views)).scalar() or 0
        
        stats = {
            'blog_posts': BlogPost.query.count(),
            'published_blog': BlogPost.query.filter_by(published=True).count(),
            'youtube_videos': YouTubeVideo.query.count(),
            'published_videos': YouTubeVideo.query.filter_by(published=True).count(),
            'podcasts': Podcast.query.count(),
            'published_podcasts': Podcast.query.filter_by(published=True).count(),
            'shorts': Short.query.count(),
            'published_shorts': Short.query.filter_by(published=True).count(),
            'community_posts': CommunityPost.query.count(),
            'published_community': CommunityPost.query.filter_by(published=True).count(),
            'total_video_views': total_video_views,
            'total_shorts_views': total_shorts_views,
            'total_views': total_video_views + total_shorts_views,
        }
        
        # Calculate gamification stats
        gamification = calculate_gamification_stats()
        current_rank, next_rank = gamification.calculate_rank()
        progress = gamification.get_progress_to_next_rank()
        
        # Get ranks and content points from database
        ranks = [r.to_dict() for r in Rank.get_all_ordered()]
        content_points = get_content_points()
        points_name = get_points_name()
        
        return render_template('admin/dashboard.html', 
                             stats=stats, 
                             sync_message=sync_message,
                             gamification=gamification,
                             current_rank=current_rank,
                             next_rank=next_rank,
                             progress=progress,
                             ranks=ranks,
                             content_points=content_points,
                             points_name=points_name)
    
    # ========== PROGRESS DASHBOARD ROUTES ==========
    
    def get_or_create_today_xp():
        """Get or create today's XP log"""
        from datetime import date
        today = date.today()
        xp_log = DailyXPLog.query.filter_by(date=today).first()
        if not xp_log:
            xp_log = DailyXPLog(date=today)
            db.session.add(xp_log)
            db.session.commit()
        return xp_log
    
    def get_or_create_current_week():
        """Get or create current week's progress with auto-calculated content counts from DB"""
        from datetime import date, timedelta
        today = date.today()
        # Get Monday of current week
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        year, week_num, _ = today.isocalendar()
        
        weekly = WeeklyProgress.query.filter_by(year=year, week_number=week_num).first()
        if not weekly:
            weekly = WeeklyProgress(
                year=year,
                week_number=week_num,
                week_start=week_start,
                week_end=week_end
            )
            db.session.add(weekly)
        
        # Auto-calculate content counts from database for this week
        # Convert dates to datetime for comparison with created_at fields
        from datetime import datetime
        week_start_dt = datetime.combine(week_start, datetime.min.time())
        week_end_dt = datetime.combine(week_end, datetime.max.time())
        
        # Count Long Form videos (duration > 60 seconds, published this week)
        long_form_count = YouTubeVideo.query.filter(
            YouTubeVideo.published == True,
            YouTubeVideo.created_at >= week_start_dt,
            YouTubeVideo.created_at <= week_end_dt,
            YouTubeVideo.duration_seconds > 60  # Exclude shorts
        ).count()
        
        # Count Shorts (duration <= 60 seconds OR from Short model, published this week)
        shorts_count = Short.query.filter(
            Short.published == True,
            Short.created_at >= week_start_dt,
            Short.created_at <= week_end_dt
        ).count()
        
        # Count Blog posts published this week
        blog_count = BlogPost.query.filter(
            BlogPost.published == True,
            BlogPost.created_at >= week_start_dt,
            BlogPost.created_at <= week_end_dt
        ).count()
        
        # Count Podcast episodes published this week
        podcast_count = Podcast.query.filter(
            Podcast.published == True,
            Podcast.created_at >= week_start_dt,
            Podcast.created_at <= week_end_dt
        ).count()
        
        # Update weekly progress with actual counts
        weekly.long_form_completed = long_form_count
        weekly.shorts_completed = shorts_count
        weekly.blog_completed = blog_count
        weekly.podcast_completed = podcast_count
        
        # Check for perfect week
        was_perfect = weekly.perfect_week
        weekly.check_perfect_week()
        
        # If perfect week just achieved, award bonus XP
        if weekly.perfect_week and not was_perfect and weekly.bonus_xp == 0:
            bonus = get_perfect_week_bonus()
            weekly.bonus_xp = bonus
            
            # Add bonus XP to main gamification stats
            gamification = GamificationStats.query.first()
            if gamification:
                gamification.total_points += bonus
                gamification.calculate_rank()
            
            # Update monthly perfect weeks count
            current_month = get_or_create_current_month()
            current_month.perfect_weeks += 1
        
        db.session.commit()
        return weekly
    
    def get_or_create_current_month():
        """Get or create current month's progress"""
        from datetime import date
        today = date.today()
        monthly = MonthlyProgress.query.filter_by(year=today.year, month=today.month).first()
        if not monthly:
            monthly = MonthlyProgress(year=today.year, month=today.month)
            db.session.add(monthly)
            db.session.commit()
        return monthly
    
    def get_or_create_current_year():
        """Get or create current year's milestones"""
        from datetime import date
        today = date.today()
        yearly = YearlyMilestones.query.filter_by(year=today.year).first()
        if not yearly:
            yearly = YearlyMilestones(year=today.year)
            db.session.add(yearly)
            db.session.commit()
        return yearly
    
    def get_or_create_architect_progress():
        """Get or create architect rank progress"""
        progress = ArchitectRankProgress.query.first()
        if not progress:
            progress = ArchitectRankProgress()
            db.session.add(progress)
            db.session.commit()
        return progress
    
    def calculate_streak():
        """Calculate current daily XP streak"""
        from datetime import date, timedelta
        streak = 0
        current_date = date.today()
        
        while True:
            log = DailyXPLog.query.filter_by(date=current_date).first()
            if log and log.goal_met:
                streak += 1
                current_date -= timedelta(days=1)
            else:
                break
        
        return streak
    
    def calculate_weekly_streak():
        """Calculate consecutive perfect weeks"""
        from datetime import date, timedelta
        streak = 0
        today = date.today()
        year, week_num, _ = today.isocalendar()
        
        while True:
            weekly = WeeklyProgress.query.filter_by(year=year, week_number=week_num).first()
            if weekly and weekly.perfect_week:
                streak += 1
                # Go to previous week
                week_num -= 1
                if week_num < 1:
                    year -= 1
                    week_num = 52
            else:
                break
        
        return streak
    
    @app.route('/admin/progress')
    @admin_required
    def admin_progress():
        """Progress Dashboard - Track daily XP, weekly Full House, monthly/yearly goals"""
        from datetime import date, timedelta
        
        # Get or create all progress records
        today_xp = get_or_create_today_xp()
        current_week = get_or_create_current_week()
        current_month = get_or_create_current_month()
        current_year = get_or_create_current_year()
        architect_progress = get_or_create_architect_progress()
        
        # Calculate streaks
        daily_streak = calculate_streak()
        weekly_streak = calculate_weekly_streak()
        
        # Update architect progress
        architect_progress.daily_streak = daily_streak
        architect_progress.weekly_streak = weekly_streak
        if daily_streak > architect_progress.longest_daily_streak:
            architect_progress.longest_daily_streak = daily_streak
        if weekly_streak > architect_progress.longest_weekly_streak:
            architect_progress.longest_weekly_streak = weekly_streak
        
        # Get gamification stats for subscriber count
        gamification = GamificationStats.query.first()
        subscriber_count = gamification.subscriber_count if gamification else 0
        total_content = gamification.total_content_count if gamification else 0
        
        # Calculate current architect rank
        architect_progress.calculate_current_rank(subscriber_count, total_content)
        db.session.commit()
        
        # Get recent XP logs (last 7 days)
        week_ago = date.today() - timedelta(days=7)
        recent_logs = DailyXPLog.query.filter(DailyXPLog.date >= week_ago)\
            .order_by(DailyXPLog.date.desc()).all()
        
        # Calculate week's total XP
        week_total_xp = sum(log.total_xp for log in recent_logs)
        
        # Get recent weekly progress (last 4 weeks)
        recent_weeks = WeeklyProgress.query.order_by(WeeklyProgress.week_start.desc()).limit(4).all()
        
        # Calculate current rank using existing system
        current_rank, next_rank = gamification.calculate_rank() if gamification else (None, None)
        progress = gamification.get_progress_to_next_rank() if gamification else None
        
        # Get data from database
        daily_tasks = DailyTask.get_active_tasks()
        weekly_requirements = WeeklyRequirement.get_active_requirements()
        ranks = [r.to_dict() for r in Rank.get_all_ordered()]
        daily_xp_goal = get_daily_xp_goal()
        points_name = get_points_name()
        perfect_week_bonus = get_perfect_week_bonus()
        
        return render_template('admin/progress.html',
            today_xp=today_xp,
            current_week=current_week,
            current_month=current_month,
            current_year=current_year,
            architect_progress=architect_progress,
            daily_streak=daily_streak,
            weekly_streak=weekly_streak,
            recent_logs=recent_logs,
            recent_weeks=recent_weeks,
            week_total_xp=week_total_xp,
            daily_tasks=daily_tasks,
            daily_xp_goal=daily_xp_goal,
            weekly_requirements=weekly_requirements,
            gamification=gamification,
            current_rank=current_rank,
            next_rank=next_rank,
            progress=progress,
            ranks=ranks,
            points_name=points_name,
            perfect_week_bonus=perfect_week_bonus
        )
    
    @app.route('/admin/progress/daily/toggle', methods=['POST'])
    @admin_required
    def admin_toggle_daily_task():
        """Toggle a daily XP task completion"""
        task_key = request.form.get('task')
        
        # Get task from database
        task = DailyTask.get_task(task_key)
        if not task:
            flash('Invalid task.', 'error')
            return redirect(url_for('admin_progress'))
        
        today_xp = get_or_create_today_xp()
        task_xp = task.xp_value
        
        # Get current task state before toggle
        was_completed = False
        if task_key == 'research':
            was_completed = today_xp.research_completed
            today_xp.research_completed = not today_xp.research_completed
        elif task_key == 'recording':
            was_completed = today_xp.recording_completed
            today_xp.recording_completed = not today_xp.recording_completed
        elif task_key == 'engagement':
            was_completed = today_xp.engagement_completed
            today_xp.engagement_completed = not today_xp.engagement_completed
        elif task_key == 'learning':
            was_completed = today_xp.learning_completed
            today_xp.learning_completed = not today_xp.learning_completed
        
        # Recalculate daily XP using database values
        today_xp.calculate_xp()
        
        # Update the main gamification stats with XP change
        gamification = GamificationStats.query.first()
        if not gamification:
            gamification = GamificationStats()
            db.session.add(gamification)
        
        # Add or remove XP from daily_xp_points based on toggle
        if was_completed:
            # Task was completed, now uncompleted - subtract XP
            gamification.daily_xp_points = max(0, (gamification.daily_xp_points or 0) - task_xp)
        else:
            # Task was uncompleted, now completed - add XP
            gamification.daily_xp_points = (gamification.daily_xp_points or 0) + task_xp
        
        # Recalculate total points to include daily XP
        content_total = (gamification.blog_points + gamification.shorts_points + 
                        gamification.short_longs_points + gamification.podcast_points + 
                        gamification.mid_longs_points + gamification.longs_points +
                        gamification.subscriber_points + gamification.views_points)
        gamification.total_points = content_total + gamification.daily_xp_points
        
        # Recalculate rank with new points
        gamification.calculate_rank()
        
        # Update architect progress for streak tracking
        architect = get_or_create_architect_progress()
        architect.lifetime_xp = gamification.total_points
        if today_xp.goal_met:
            architect.last_daily_log = today_xp.date
        
        db.session.commit()
        
        is_completed = not was_completed
        status = "completed" if is_completed else "uncompleted"
        points_name = get_points_name()
        flash(f'{task.name} {status}! {("+" if is_completed else "")}{task_xp if is_completed else -task_xp} {points_name} (Total: {gamification.total_points:,} {points_name})', 'success')
        return redirect(url_for('admin_progress'))
    
    
    @app.route('/admin/progress/monthly/experimental', methods=['POST'])
    @admin_required
    def admin_update_experimental():
        """Update monthly experimental content"""
        current_month = get_or_create_current_month()
        
        current_month.experimental_content = request.form.get('experimental_content', '')
        current_month.experimental_type = request.form.get('experimental_type', '')
        current_month.experimental_completed = request.form.get('experimental_completed') == 'on'
        
        db.session.commit()
        
        flash('Monthly experimental content updated!', 'success')
        return redirect(url_for('admin_progress'))
    
    @app.route('/admin/progress/milestone/toggle', methods=['POST'])
    @admin_required
    def admin_toggle_milestone():
        """Toggle an architect milestone"""
        milestone = request.form.get('milestone')
        architect = get_or_create_architect_progress()
        
        if milestone == 'collab':
            architect.collabs_completed += 1
            flash(f'Collab #{architect.collabs_completed} logged!', 'success')
        elif milestone == 'series':
            architect.series_launched += 1
            flash(f'Series #{architect.series_launched} launched!', 'success')
        elif milestone == 'revenue':
            architect.revenue_achieved = not architect.revenue_achieved
            status = "achieved" if architect.revenue_achieved else "removed"
            flash(f'Revenue milestone {status}!', 'success')
        elif milestone == 'team':
            architect.team_hired = not architect.team_hired
            status = "achieved" if architect.team_hired else "removed"
            flash(f'Team hiring milestone {status}!', 'success')
        elif milestone == 'viral':
            architect.viral_video_achieved = not architect.viral_video_achieved
            status = "achieved" if architect.viral_video_achieved else "removed"
            flash(f'Viral video milestone {status}!', 'success')
        
        # Recalculate rank
        gamification = GamificationStats.query.first()
        subscriber_count = gamification.subscriber_count if gamification else 0
        total_content = gamification.total_content_count if gamification else 0
        architect.calculate_current_rank(subscriber_count, total_content)
        
        db.session.commit()
        return redirect(url_for('admin_progress'))
    
    # Blog management
    @app.route('/admin/blog')
    @admin_required
    def admin_blog_list():
        """Admin blog posts list"""
        posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
        ideas_count = TopicIdea.query.filter_by(reviewed=False).count()
        return render_template('admin/blog_list.html', posts=posts, ideas_count=ideas_count)
    
    @app.route('/admin/blog/new', methods=['GET', 'POST'])
    @admin_required
    def admin_blog_new():
        """Create new blog post"""
        if request.method == 'POST':
            title = request.form.get('title')
            slug = request.form.get('slug') or title.lower().replace(' ', '-')
            excerpt = request.form.get('excerpt')
            content = request.form.get('content')
            featured_image = request.form.get('featured_image')
            author = request.form.get('author', 'Cryptasium Team')
            published = request.form.get('published') == 'on'
            
            post = BlogPost(
                title=title,
                slug=slug,
                excerpt=excerpt,
                content=content,
                featured_image=featured_image,
                author=author,
                published=published
            )
            
            db.session.add(post)
            db.session.commit()
            flash('Blog post created successfully!', 'success')
            return redirect(url_for('admin_blog_list'))
        
        return render_template('admin/blog_form.html')
    
    @app.route('/admin/blog/<int:id>/edit', methods=['GET', 'POST'])
    @admin_required
    def admin_blog_edit(id):
        """Edit blog post"""
        post = BlogPost.query.get_or_404(id)
        
        if request.method == 'POST':
            post.title = request.form.get('title')
            post.slug = request.form.get('slug')
            post.excerpt = request.form.get('excerpt')
            post.content = request.form.get('content')
            post.featured_image = request.form.get('featured_image')
            post.author = request.form.get('author')
            post.published = request.form.get('published') == 'on'
            post.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash('Blog post updated successfully!', 'success')
            return redirect(url_for('admin_blog_list'))
        
        return render_template('admin/blog_form.html', post=post)
    
    @app.route('/admin/blog/<int:id>/toggle', methods=['POST'])
    @admin_required
    def admin_blog_toggle(id):
        """Toggle blog post published status"""
        post = BlogPost.query.get_or_404(id)
        post.published = not post.published
        db.session.commit()
        flash(f'Post {"published" if post.published else "unpublished"} successfully!', 'success')
        return redirect(url_for('admin_blog_list'))
    
    @app.route('/admin/blog/<int:id>/delete', methods=['POST'])
    @admin_required
    def admin_blog_delete(id):
        """Delete blog post"""
        post = BlogPost.query.get_or_404(id)
        db.session.delete(post)
        db.session.commit()
        flash('Blog post deleted successfully!', 'success')
        return redirect(url_for('admin_blog_list'))
    
    # YouTube management (similar pattern)
    @app.route('/admin/youtube')
    @admin_required
    def admin_youtube_list():
        """Admin YouTube videos list"""
        videos = YouTubeVideo.query.order_by(YouTubeVideo.created_at.desc()).all()
        return render_template('admin/youtube_list.html', videos=videos)
    
    @app.route('/admin/youtube/new', methods=['GET', 'POST'])
    @admin_required
    def admin_youtube_new():
        """Create new YouTube video"""
        if request.method == 'POST':
            video = YouTubeVideo(
                title=request.form.get('title'),
                description=request.form.get('description'),
                video_id=request.form.get('video_id'),
                thumbnail_url=request.form.get('thumbnail_url'),
                duration=request.form.get('duration'),
                published=request.form.get('published') == 'on'
            )
            db.session.add(video)
            db.session.commit()
            flash('YouTube video added successfully!', 'success')
            return redirect(url_for('admin_youtube_list'))
        return render_template('admin/youtube_form.html')
    
    @app.route('/admin/youtube/<int:id>/edit', methods=['GET', 'POST'])
    @admin_required
    def admin_youtube_edit(id):
        """Edit YouTube video"""
        video = YouTubeVideo.query.get_or_404(id)
        if request.method == 'POST':
            video.title = request.form.get('title')
            video.description = request.form.get('description')
            video.video_id = request.form.get('video_id')
            video.thumbnail_url = request.form.get('thumbnail_url')
            video.duration = request.form.get('duration')
            video.published = request.form.get('published') == 'on'
            db.session.commit()
            flash('YouTube video updated successfully!', 'success')
            return redirect(url_for('admin_youtube_list'))
        return render_template('admin/youtube_form.html', video=video)
    
    @app.route('/admin/youtube/<int:id>/toggle', methods=['POST'])
    @admin_required
    def admin_youtube_toggle(id):
        """Toggle YouTube video publish status"""
        video = YouTubeVideo.query.get_or_404(id)
        video.published = not video.published
        db.session.commit()
        status = 'published' if video.published else 'unpublished'
        flash(f'Video {status} successfully!', 'success')
        return redirect(url_for('admin_youtube_list'))
    
    @app.route('/admin/youtube/<int:id>/delete', methods=['POST'])
    @admin_required
    def admin_youtube_delete(id):
        """Delete YouTube video"""
        video = YouTubeVideo.query.get_or_404(id)
        db.session.delete(video)
        db.session.commit()
        flash('YouTube video deleted successfully!', 'success')
        return redirect(url_for('admin_youtube_list'))
    
    @app.route('/admin/youtube/sync', methods=['POST'])
    @admin_required
    def admin_youtube_sync():
        """Sync videos from YouTube channel"""
        videos, shorts, error = youtube_service.fetch_channel_videos(max_results=50)
        
        if error:
            flash(f'Sync failed: {error}', 'error')
            return redirect(url_for('admin_youtube_list'))
        
        videos_added = 0
        videos_updated = 0
        shorts_added = 0
        shorts_updated = 0
        
        # Add or update videos
        for video_data in videos:
            existing = YouTubeVideo.query.filter_by(video_id=video_data['video_id']).first()
            duration_seconds = video_data.get('duration_seconds', 0)
            content_type = get_video_content_type(duration_seconds)
            
            if existing:
                # Update existing video with latest stats
                existing.title = video_data['title']
                existing.thumbnail_url = video_data['thumbnail_url']
                existing.duration = video_data['duration']
                existing.duration_seconds = duration_seconds
                existing.content_type = content_type
                existing.views = video_data.get('view_count', 0)
                videos_updated += 1
            else:
                video = YouTubeVideo(
                    title=video_data['title'],
                    description=video_data['description'][:500] if video_data['description'] else '',
                    video_id=video_data['video_id'],
                    thumbnail_url=video_data['thumbnail_url'],
                    duration=video_data['duration'],
                    duration_seconds=duration_seconds,
                    content_type=content_type,
                    views=video_data.get('view_count', 0),
                    published=True,
                    created_at=video_data['published_at']
                )
                db.session.add(video)
                videos_added += 1
        
        # Add or update shorts
        for short_data in shorts:
            existing = Short.query.filter_by(video_id=short_data['video_id']).first()
            if existing:
                # Update existing short with latest stats
                existing.title = short_data['title']
                existing.thumbnail_url = short_data['thumbnail_url']
                existing.duration = short_data['duration']
                existing.views = short_data.get('view_count', 0)
                shorts_updated += 1
            else:
                short = Short(
                    title=short_data['title'],
                    description=short_data['description'][:500] if short_data['description'] else '',
                    video_id=short_data['video_id'],
                    thumbnail_url=short_data['thumbnail_url'],
                    duration=short_data['duration'],
                    views=short_data.get('view_count', 0),
                    published=True,
                    created_at=short_data['published_at']
                )
                db.session.add(short)
                shorts_added += 1
        
        db.session.commit()
        
        # Also sync channel subscriber stats
        channel_stats, channel_error = sync_channel_stats()
        subscriber_msg = ""
        if channel_stats:
            subscriber_msg = f" Subscribers: {channel_stats.subscriber_count:,}"
        
        # Recalculate gamification stats
        calculate_gamification_stats()
        
        if videos_added or shorts_added or videos_updated or shorts_updated:
            flash(f'Synced successfully! Added {videos_added} videos, {shorts_added} shorts. Updated {videos_updated} videos, {shorts_updated} shorts.{subscriber_msg}', 'success')
        else:
            flash(f'Sync complete. No changes detected.{subscriber_msg}', 'success')
        
        return redirect(url_for('admin_youtube_list'))
    
    @app.route('/admin/shorts/sync', methods=['POST'])
    @admin_required
    def admin_shorts_sync():
        """Sync shorts from YouTube channel (redirects to main sync)"""
        videos, shorts, error = youtube_service.fetch_channel_videos(max_results=50)
        
        if error:
            flash(f'Sync failed: {error}', 'error')
            return redirect(url_for('admin_shorts_list'))
        
        shorts_added = 0
        
        # Add new shorts
        for short_data in shorts:
            existing = Short.query.filter_by(video_id=short_data['video_id']).first()
            if not existing:
                short = Short(
                    title=short_data['title'],
                    description=short_data['description'][:500] if short_data['description'] else '',
                    video_id=short_data['video_id'],
                    thumbnail_url=short_data['thumbnail_url'],
                    duration=short_data['duration'],
                    published=True,
                    created_at=short_data['published_at']
                )
                db.session.add(short)
                shorts_added += 1
        
        db.session.commit()
        
        if shorts_added:
            flash(f'Synced successfully! Added {shorts_added} shorts.', 'success')
        else:
            flash('No new shorts to sync. All shorts are already imported.', 'success')
        
        return redirect(url_for('admin_shorts_list'))
    
    # Podcast management
    @app.route('/admin/podcast')
    @admin_required
    def admin_podcast_list():
        """Admin podcast episodes list"""
        podcasts = Podcast.query.order_by(Podcast.created_at.desc()).all()
        return render_template('admin/podcast_list.html', podcasts=podcasts)
    
    @app.route('/admin/podcast/new', methods=['GET', 'POST'])
    @admin_required
    def admin_podcast_new():
        """Create new podcast episode"""
        if request.method == 'POST':
            podcast = Podcast(
                title=request.form.get('title'),
                description=request.form.get('description'),
                episode_number=int(request.form.get('episode_number') or 0),
                audio_url=request.form.get('audio_url'),
                thumbnail_url=request.form.get('thumbnail_url'),
                duration=request.form.get('duration'),
                published=request.form.get('published') == 'on'
            )
            db.session.add(podcast)
            db.session.commit()
            flash('Podcast episode added successfully!', 'success')
            return redirect(url_for('admin_podcast_list'))
        return render_template('admin/podcast_form.html')
    
    @app.route('/admin/podcast/<int:id>/edit', methods=['GET', 'POST'])
    @admin_required
    def admin_podcast_edit(id):
        """Edit podcast episode"""
        podcast = Podcast.query.get_or_404(id)
        if request.method == 'POST':
            podcast.title = request.form.get('title')
            podcast.description = request.form.get('description')
            podcast.episode_number = int(request.form.get('episode_number') or 0)
            podcast.audio_url = request.form.get('audio_url')
            podcast.thumbnail_url = request.form.get('thumbnail_url')
            podcast.duration = request.form.get('duration')
            podcast.published = request.form.get('published') == 'on'
            db.session.commit()
            flash('Podcast episode updated successfully!', 'success')
            return redirect(url_for('admin_podcast_list'))
        return render_template('admin/podcast_form.html', podcast=podcast)
    
    @app.route('/admin/podcast/<int:id>/delete', methods=['POST'])
    @admin_required
    def admin_podcast_delete(id):
        """Delete podcast episode"""
        podcast = Podcast.query.get_or_404(id)
        db.session.delete(podcast)
        db.session.commit()
        flash('Podcast episode deleted successfully!', 'success')
        return redirect(url_for('admin_podcast_list'))
    
    # Shorts management
    @app.route('/admin/shorts')
    @admin_required
    def admin_shorts_list():
        """Admin shorts list"""
        shorts = Short.query.order_by(Short.created_at.desc()).all()
        return render_template('admin/shorts_list.html', shorts=shorts)
    
    @app.route('/admin/shorts/new', methods=['GET', 'POST'])
    @admin_required
    def admin_shorts_new():
        """Create new short"""
        if request.method == 'POST':
            short = Short(
                title=request.form.get('title'),
                description=request.form.get('description'),
                video_id=request.form.get('video_id'),
                thumbnail_url=request.form.get('thumbnail_url'),
                duration=request.form.get('duration'),
                published=request.form.get('published') == 'on'
            )
            db.session.add(short)
            db.session.commit()
            flash('Short added successfully!', 'success')
            return redirect(url_for('admin_shorts_list'))
        return render_template('admin/shorts_form.html')
    
    @app.route('/admin/shorts/<int:id>/edit', methods=['GET', 'POST'])
    @admin_required
    def admin_shorts_edit(id):
        """Edit short"""
        short = Short.query.get_or_404(id)
        if request.method == 'POST':
            short.title = request.form.get('title')
            short.description = request.form.get('description')
            short.video_id = request.form.get('video_id')
            short.thumbnail_url = request.form.get('thumbnail_url')
            short.duration = request.form.get('duration')
            short.published = request.form.get('published') == 'on'
            db.session.commit()
            flash('Short updated successfully!', 'success')
            return redirect(url_for('admin_shorts_list'))
        return render_template('admin/shorts_form.html', short=short)
    
    @app.route('/admin/shorts/<int:id>/toggle', methods=['POST'])
    @admin_required
    def admin_shorts_toggle(id):
        """Toggle short publish status"""
        short = Short.query.get_or_404(id)
        short.published = not short.published
        db.session.commit()
        status = 'published' if short.published else 'unpublished'
        flash(f'Short {status} successfully!', 'success')
        return redirect(url_for('admin_shorts_list'))
    
    @app.route('/admin/shorts/<int:id>/delete', methods=['POST'])
    @admin_required
    def admin_shorts_delete(id):
        """Delete short"""
        short = Short.query.get_or_404(id)
        db.session.delete(short)
        db.session.commit()
        flash('Short deleted successfully!', 'success')
        return redirect(url_for('admin_shorts_list'))
    
    # Community management
    @app.route('/admin/community')
    @admin_required
    def admin_community_list():
        """Admin community posts list"""
        posts = CommunityPost.query.order_by(CommunityPost.created_at.desc()).all()
        return render_template('admin/community_list.html', posts=posts)
    
    @app.route('/admin/ideas')
    @admin_required
    def admin_ideas_list():
        """Admin topic ideas list"""
        ideas = TopicIdea.query.order_by(TopicIdea.created_at.desc()).all()
        return render_template('admin/ideas_list.html', ideas=ideas)
    
    @app.route('/admin/ideas/<int:id>/approve', methods=['POST'])
    @admin_required
    def admin_ideas_approve(id):
        """Approve a topic idea"""
        idea = TopicIdea.query.get_or_404(id)
        idea.status = 'approved'
        idea.reviewed = True
        idea.reviewed_at = datetime.utcnow()
        db.session.commit()
        flash(f'Topic idea "{idea.topic}" approved!', 'success')
        return redirect(url_for('admin_ideas_list'))
    
    @app.route('/admin/ideas/<int:id>/reject', methods=['POST'])
    @admin_required
    def admin_ideas_reject(id):
        """Reject a topic idea"""
        idea = TopicIdea.query.get_or_404(id)
        idea.status = 'rejected'
        idea.reviewed = True
        idea.reviewed_at = datetime.utcnow()
        db.session.commit()
        flash(f'Topic idea "{idea.topic}" rejected.', 'success')
        return redirect(url_for('admin_ideas_list'))
    
    @app.route('/admin/ideas/<int:id>/pending', methods=['POST'])
    @admin_required
    def admin_ideas_pending(id):
        """Set idea back to pending"""
        idea = TopicIdea.query.get_or_404(id)
        idea.status = 'pending'
        idea.reviewed = False
        idea.reviewed_at = None
        db.session.commit()
        flash(f'Topic idea "{idea.topic}" set back to pending.', 'success')
        return redirect(url_for('admin_ideas_list'))
    
    @app.route('/admin/ideas/<int:id>/delete', methods=['POST'])
    @admin_required
    def admin_ideas_delete(id):
        """Delete a topic idea"""
        idea = TopicIdea.query.get_or_404(id)
        topic = idea.topic
        db.session.delete(idea)
        db.session.commit()
        flash(f'Topic idea "{topic}" deleted.', 'success')
        return redirect(url_for('admin_ideas_list'))
    
    @app.route('/admin/community/new', methods=['GET', 'POST'])
    @admin_required
    def admin_community_new():
        """Create new community post"""
        if request.method == 'POST':
            post = CommunityPost(
                title=request.form.get('title'),
                content=request.form.get('content'),
                author=request.form.get('author', 'Community Member'),
                category=request.form.get('category'),
                published=request.form.get('published') == 'on'
            )
            db.session.add(post)
            db.session.commit()
            flash('Community post created successfully!', 'success')
            return redirect(url_for('admin_community_list'))
        return render_template('admin/community_form.html')
    
    @app.route('/admin/community/<int:id>/edit', methods=['GET', 'POST'])
    @admin_required
    def admin_community_edit(id):
        """Edit community post"""
        post = CommunityPost.query.get_or_404(id)
        if request.method == 'POST':
            post.title = request.form.get('title')
            post.content = request.form.get('content')
            post.author = request.form.get('author')
            post.category = request.form.get('category')
            post.published = request.form.get('published') == 'on'
            db.session.commit()
            flash('Community post updated successfully!', 'success')
            return redirect(url_for('admin_community_list'))
        return render_template('admin/community_form.html', post=post)
    
    @app.route('/admin/community/<int:id>/delete', methods=['POST'])
    @admin_required
    def admin_community_delete(id):
        """Delete community post"""
        post = CommunityPost.query.get_or_404(id)
        db.session.delete(post)
        db.session.commit()
        flash('Community post deleted successfully!', 'success')
        return redirect(url_for('admin_community_list'))
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0')

