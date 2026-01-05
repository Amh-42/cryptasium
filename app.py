"""
Main Flask application for Cryptasium
Fully Dynamic Gamification System
"""
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from functools import wraps
from datetime import datetime, date, timedelta
import os
import markdown
import json

from config import config
from models import (
    db, BlogPost, YouTubeVideo, Podcast, Short, CommunityPost, TopicIdea,
    SystemSettings, User, TrackableType, TrackableEntry, CustomRank, RankCondition,
    UserDailyTask, TaskCompletion, DailyLog, Achievement, UserAchievement, Streak,
    UserSettings, ContentCalendarEntry, init_user_gamification, DashboardImage
)
import youtube_service
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename




def create_app(config_name=None):
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Load configuration
    config_name = config_name or os.environ.get('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])
    
    # Initialize database
    db.init_app(app)

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'admin_login'


    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    # Register markdown filter
    @app.template_filter('markdown')
    def markdown_filter(text):
        if not text:
            return ''
        try:
            import re
            text = re.sub(r'\[\[([^\]]+)\]\]', r'[\1](\1)', text)
            text = re.sub(r'!\[\[([^\]]+)\]\]', r'![\1](\1)', text)
            text = re.sub(r'==([^=]+)==', r'<mark>\1</mark>', text)
            extensions = ['fenced_code', 'tables', 'nl2br', 'sane_lists']
            try:
                import pygments
                extensions.append('codehilite')
            except ImportError:
                pass
            md = markdown.Markdown(extensions=extensions)
            result = md.convert(str(text))
            md.reset()
            return result
        except Exception:
            import html
            return html.escape(str(text))
    
    @app.template_filter('format_number')
    def format_number_filter(value):
        try:
            num = int(value)
            if num >= 1_000_000_000:
                return f"{num / 1_000_000_000:.1f}B".rstrip('0').rstrip('.')
            elif num >= 1_000_000:
                return f"{num / 1_000_000:.1f}M".rstrip('0').rstrip('.')
            elif num >= 1_000:
                return f"{num / 1_000:.1f}K".rstrip('0').rstrip('.')
            else:
                return str(num)
        except (ValueError, TypeError):
            return str(value)
    
    @app.context_processor
    def inject_settings():
        if current_user.is_authenticated:
            settings = UserSettings.query.filter_by(user_id=current_user.id).first()
            points_name = settings.points_name if settings and settings.points_name else 'XP'
            return dict(settings=settings, points_name=points_name)
        return dict(settings=None, points_name='XP')

    # ========== DECORATORS ==========
    
    def admin_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('admin_login'))
            return f(*args, **kwargs)
        return decorated_function

    # ========== SOCKETIO HELPERS & EVENTS ==========


    @app.route('/admin/trackable/action', methods=['POST'])
    @admin_required
    def admin_trackable_action():
        data = request.form
        trackable_id = data.get('id')
        action = data.get('action', 'increment')
        value = float(data.get('value', 0))
        
        trackable = TrackableType.query.get_or_404(trackable_id)
        if trackable.user_id != current_user.id:
            abort(403)
            
        allocated_condition_id = data.get('allocated_condition_id')
        if allocated_condition_id:
            allocated_condition_id = int(allocated_condition_id)

        # Check for ambiguity (Allocation)
        if action == 'increment' and not allocated_condition_id:
             stats = get_user_stats()
             next_rank = stats['next_rank']
             if next_rank:
                 candidates = [c for c in next_rank.conditions if c.condition_type == 'total_xp']
                 if len(candidates) >= 2:
                     if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                         return jsonify({
                             'success': False,
                             'status': 'ambiguous',
                             'message': 'Select where to add XP',
                             'conditions': [{'id': c.id, 'name': c.custom_name or 'Total XP'} for c in candidates]
                         })
                 elif len(candidates) == 1:
                     allocated_condition_id = candidates[0].id

        if action == 'decrement':
            last_entry = TrackableEntry.query.filter_by(
                user_id=current_user.id,
                trackable_type_id=trackable_id,
                date=date.today()
            ).order_by(TrackableEntry.id.desc()).first()
            if last_entry:
                db.session.delete(last_entry)
        else:
            entry = TrackableEntry(
                user_id=current_user.id,
                trackable_type_id=trackable_id,
                date=date.today(),
                count=1,
                value=value,
                allocated_condition_id=allocated_condition_id
            )
            db.session.add(entry)
            
            streak = Streak.query.filter_by(
                user_id=current_user.id,
                streak_type='daily_xp'
            ).first()
            if not streak:
                streak = Streak(user_id=current_user.id, streak_type='daily_xp', current_count=0, longest_count=0)
                db.session.add(streak)
            streak.update_streak(date.today())
            
        # Check rank update
        did_level_up, new_rank = current_user.check_rank_update()
            
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
             today_log = DailyLog.query.filter_by(user_id=current_user.id, date=date.today()).first()
             return jsonify({
                 'success': True,
                 'total_count': trackable.get_total_count(), # Approximation or fetch fresh
                 'total_xp': trackable.get_total_xp(),
                 'total_value': trackable.get_total_value(),
                 'today_xp': today_log.total_xp if today_log else 0
             })
        return redirect(url_for('admin_dashboard'))

    @app.route('/admin/task/action', methods=['POST'])
    @admin_required
    def admin_task_action():
        data = request.form
        slug = data.get('slug')
        action = data.get('action', 'toggle')
        allocated_condition_id = data.get('allocated_condition_id')
        if allocated_condition_id:
            allocated_condition_id = int(allocated_condition_id)
        
        task = UserDailyTask.query.filter_by(
            user_id=current_user.id,
            slug=slug
        ).first()
        if not task:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'Task not found'}), 404
            abort(404)

        # Check for ambiguity
        today = date.today()
        should_check = False
        if action == 'increment':
            should_check = True
        elif task.task_type == 'normal' and action == 'toggle':
             existing = TaskCompletion.query.filter_by(
                user_id=current_user.id,
                task_id=task.id,
                date=today
            ).first()
             if not existing:
                 should_check = True

        # Auto-allocate or Ask
        if should_check and not allocated_condition_id:
             stats = get_user_stats()
             next_rank = stats['next_rank']
             if next_rank:
                 candidates = [c for c in next_rank.conditions if c.condition_type == 'total_xp']
                 if len(candidates) >= 2:
                     if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                         return jsonify({
                             'success': False,
                             'status': 'ambiguous',
                             'message': 'Select where to add XP',
                             'conditions': [{'id': c.id, 'name': c.custom_name or 'Total XP'} for c in candidates]
                         })
                 elif len(candidates) == 1:
                     # Exact match logic: If there is exactly one bucket for XP, use it automatically
                     # The user said: "if don't specify ... added to the first total xp condition"
                     allocated_condition_id = candidates[0].id
        
        if task.task_type == 'count':
            current_count = task.get_today_completion_count(today)
            if action == 'decrement':
                if current_count > 0:
                    last_completion = TaskCompletion.query.filter_by(
                        user_id=current_user.id,
                        task_id=task.id,
                        date=today
                    ).order_by(TaskCompletion.id.desc()).first()
                    if last_completion:
                        db.session.delete(last_completion)
            else:
                if current_count < task.target_count:
                    completion = TaskCompletion(
                        user_id=current_user.id,
                        task_id=task.id,
                        date=today,
                        count=1,
                        allocated_condition_id=allocated_condition_id
                    )
                    xp_e = task.xp_per_count if task.xp_per_count > 0 else (task.xp_value if current_count + 1 >= task.target_count else 0)
                    completion.xp_earned = xp_e
                    db.session.add(completion)
        else:
            existing = TaskCompletion.query.filter_by(
                user_id=current_user.id,
                task_id=task.id,
                date=today
            ).first()
            if existing:
                db.session.delete(existing)
            else:
                completion = TaskCompletion(
                    user_id=current_user.id,
                    task_id=task.id,
                    date=today,
                    xp_earned=task.xp_value,
                    allocated_condition_id=allocated_condition_id
                )
                db.session.add(completion)
                if task.repeat_type == 'ebbinghaus':
                    task.calculate_next_ebbinghaus_date()
                if task.repeat_type in ('once', 'none'):
                    task.completed_date = today

        today_log = DailyLog.query.filter_by(user_id=current_user.id, date=today).first()
        if not today_log:
            today_log = DailyLog(user_id=current_user.id, date=today)
            db.session.add(today_log)
        
        db.session.flush()
        
        total_task_xp = db.session.query(db.func.sum(TaskCompletion.xp_earned)).filter(
            TaskCompletion.user_id == current_user.id,
            TaskCompletion.date == today
        ).scalar() or 0
        today_log.total_xp = total_task_xp
        
        settings = UserSettings.query.filter_by(user_id=current_user.id).first()
        if settings and today_log.total_xp >= settings.daily_xp_goal:
            today_log.goal_met = True
        else:
            today_log.goal_met = False
            
        streak = Streak.query.filter_by(user_id=current_user.id, streak_type='daily_xp').first()
        if not streak:
            streak = Streak(user_id=current_user.id, streak_type='daily_xp', current_count=0, longest_count=0)
            db.session.add(streak)
        streak.update_streak(today)
        
        # Check for rank update
        did_level_up, new_rank = current_user.check_rank_update()
        
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
             return jsonify({
                 'success': True,
                 'total_xp': today_log.total_xp,
                 'goal_met': today_log.goal_met,
                 'current_count': task.get_today_completion_count(today) if task.task_type == 'count' else 0,
                 'is_completed': task.is_completed_today(today)
             })
             
        return redirect(url_for('admin_dashboard'))
    
    # ========== HELPER FUNCTIONS ==========
    
    def sync_youtube_data(user_id):
        """
        Fetch latest data from YouTube API and update database.
        Includes a cooldown to avoid excessive API calls.
        """
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"
            
        # Check if YouTube sync is enabled in settings
        settings = UserSettings.query.filter_by(user_id=user_id).first()
        if not settings or not settings.enable_youtube_sync:
            return False, "YouTube sync is disabled in settings"
        
        # Check cooldown (sync at most once every 10 minutes)
        if user.last_youtube_sync:
            cooldown_time = timedelta(minutes=10)
            if datetime.utcnow() - user.last_youtube_sync < cooldown_time:
                return True, "Synced recently"
        
        try:
            # 1. Sync channel statistics
            stats, error = youtube_service.fetch_channel_statistics()
            if stats:
                user.youtube_subscribers = stats.get('subscriber_count', 0)
                user.youtube_channel_views = stats.get('view_count', 0)
            
            # 2. Sync videos and shorts
            videos, shorts, error = youtube_service.fetch_channel_videos(max_results=20)
            
            # Update regular videos
            for v_data in videos:
                existing = YouTubeVideo.query.filter_by(video_id=v_data['video_id']).first()
                if existing:
                    existing.title = v_data['title']
                    existing.views = v_data['view_count']
                    existing.thumbnail_url = v_data['thumbnail_url']
                else:
                    new_video = YouTubeVideo(
                        video_id=v_data['video_id'],
                        title=v_data['title'],
                        description=v_data['description'],
                        thumbnail_url=v_data['thumbnail_url'],
                        duration=v_data['duration'],
                        duration_seconds=v_data['duration_seconds'],
                        views=v_data['view_count'],
                        published=True,
                        user_id=user_id
                    )
                    db.session.add(new_video)
            
            # Update shorts
            for s_data in shorts:
                existing = Short.query.filter_by(video_id=s_data['video_id']).first()
                if existing:
                    existing.title = s_data['title']
                    existing.views = s_data['view_count']
                    existing.thumbnail_url = s_data['thumbnail_url']
                else:
                    new_short = Short(
                        video_id=s_data['video_id'],
                        title=s_data['title'],
                        description=s_data['description'],
                        thumbnail_url=s_data['thumbnail_url'],
                        duration=s_data['duration'],
                        views=s_data['view_count'],
                        published=True,
                        user_id=user_id
                    )
                    db.session.add(new_short)
            
            user.last_youtube_sync = datetime.utcnow()
            db.session.commit()
            return True, "Successfully synced with YouTube"
            
        except Exception as e:
            db.session.rollback()
            return False, f"Sync failed: {str(e)}"

    def get_user_stats():
        """Get comprehensive stats for the current user"""
        if not current_user.is_authenticated:
            return None

        # Get trackable types and their totals
        trackables = TrackableType.query.filter_by(
            user_id=current_user.id, 
            is_active=True
        ).order_by(TrackableType.display_order).all()
        
        # Calculate total XP using centralization method on User model
        total_xp = current_user.get_total_xp()
        
        # Get current rank and next rank
        # Sort by level to determine order
        ranks = CustomRank.query.filter_by(
            user_id=current_user.id
        ).order_by(CustomRank.level.desc()).all()
        
        current_rank = None
        next_rank = None
        rank_progress_details = None
        
        # Determine current rank by checking conditions from highest level downwards
        for i, rank in enumerate(ranks):
            is_met, details = rank.check_conditions_met(current_user.id)
            if is_met:
                current_rank = rank
                break
        
        current_level = current_rank.level if current_rank else 0
        
        # Find next rank
        # Look for the immediate next level rank
        next_rank = CustomRank.query.filter_by(
            user_id=current_user.id,
            level=current_level + 1
        ).first()
        
        if not next_rank and (not current_rank or not current_rank.is_max_rank):
            # If no specific next level, find the lowest level rank that is higher than current
            next_rank = CustomRank.query.filter(
                CustomRank.user_id == current_user.id,
                CustomRank.level > current_level
            ).order_by(CustomRank.level.asc()).first()
        
        # Calculate progress to next rank
        progress_percent = 0
        if next_rank:
            is_met, progress_details = next_rank.check_conditions_met(current_user.id)
            rank_progress_details = progress_details
            
            # For progress bar, calculate an average completion percentage if multiple conditions
            # Check for multi-condition dict format (dict of dicts)
            if progress_details and any(isinstance(v, dict) for v in progress_details.values()):
                total_progress = 0
                condition_count = 0
                for cond_id, info in progress_details.items():
                    if isinstance(info, dict) and 'met' in info:
                        threshold = info.get('threshold', 1) or 1
                        current = info.get('current', 0) or 0
                        # Cap at 100% per condition
                        total_progress += min(1.0, float(current) / float(threshold))
                        condition_count += 1
                
                if condition_count > 0:
                    progress_percent = int((total_progress / condition_count) * 100)
            elif next_rank.min_xp is not None: # Fallback for legacy
                prev_xp = (current_rank.min_xp or 0) if current_rank else 0
                xp_in_rank = total_xp - prev_xp
                xp_needed = (next_rank.min_xp or 0) - prev_xp
                if xp_needed > 0:
                    progress_percent = min(100, int((xp_in_rank / xp_needed) * 100))
        elif current_rank and current_rank.is_max_rank:
            progress_percent = 100
        
        # Get streak
        streak = Streak.query.filter_by(
            user_id=current_user.id, 
            streak_type='daily_xp'
        ).first()
        
        # Get settings
        settings = UserSettings.query.filter_by(user_id=current_user.id).first()
        
        # Get today's log
        today_log = DailyLog.query.filter_by(
            user_id=current_user.id,
            date=date.today()
        ).first()
        
        # Get set of unlocked rank IDs for easy lookup in templates
        unlocked_rank_ids = []
        if current_rank:
            unlocked_rank_ids = [r.id for r in ranks if r.level <= current_rank.level]
        
        return {
            'today_xp': today_log.total_xp if today_log else 0,
            'daily_goal': settings.daily_xp_goal if settings else 50,
            'goal_met': today_log.goal_met if today_log else False,
            'total_xp': total_xp,
            'trackables': trackables,
            'current_rank': current_rank,
            'next_rank': next_rank,
            'progress_percent': progress_percent,
            'rank_progress_details': rank_progress_details,
            'ranks': list(reversed(ranks)),
            'unlocked_rank_ids': unlocked_rank_ids,
            'streak': streak,
            'settings': settings,
            'today_log': today_log,
            'points_name': 'XP',
            'youtube': {
                'subscribers': current_user.youtube_subscribers or 0,
                'channel_views': current_user.youtube_channel_views or 0,
                'last_sync': current_user.last_youtube_sync
            }
        }
    
    def get_weekly_stats():
        """Get this week's stats"""
        if not current_user.is_authenticated:
            return {}
        
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        # Get entries for this week
        entries = TrackableEntry.query.filter(
            TrackableEntry.user_id == current_user.id,
            TrackableEntry.date >= week_start,
            TrackableEntry.date <= week_end
        ).all()
        
        # Group by type
        by_type = {}
        for entry in entries:
            if entry.trackable_type:
                slug = entry.trackable_type.slug
                if slug not in by_type:
                    by_type[slug] = {'count': 0, 'xp': 0, 'type': entry.trackable_type}
                by_type[slug]['count'] += entry.count
                by_type[slug]['xp'] += entry.get_xp()
        
        # Get daily logs for this week
        daily_logs = DailyLog.query.filter(
            DailyLog.user_id == current_user.id,
            DailyLog.date >= week_start,
            DailyLog.date <= week_end
        ).all()
        
        days_with_goal_met = sum(1 for log in daily_logs if log.goal_met)
        
        return {
            'week_start': week_start,
            'week_end': week_end,
            'by_type': by_type,
            'daily_logs': daily_logs,
            'days_with_goal_met': days_with_goal_met,
            'perfect_week': days_with_goal_met >= 7
        }
    
    # ========== PUBLIC ROUTES ==========
    
    @app.route('/')
    def index():
        latest_blog = BlogPost.query.filter_by(published=True).order_by(BlogPost.created_at.desc()).first()
        latest_videos = YouTubeVideo.query.filter_by(published=True).order_by(YouTubeVideo.created_at.desc()).limit(3).all()
        latest_shorts = Short.query.filter_by(published=True).order_by(Short.created_at.desc()).limit(3).all()
        return render_template('index.html', latest_blog=latest_blog, latest_videos=latest_videos, latest_shorts=latest_shorts)

    @app.route('/blog')
    def blog_list():
        page = request.args.get('page', 1, type=int)
        posts = BlogPost.query.filter_by(published=True).order_by(BlogPost.created_at.desc()).paginate(page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
        return render_template('blog.html', posts=posts)

    @app.route('/blog/<slug>')
    def blog_detail(slug):
        post = BlogPost.query.filter_by(slug=slug).first()
        if not post or not post.published:
            abort(404)
        post.views = (post.views or 0) + 1
        db.session.commit()
        return render_template('post_detail.html', post=post)

    @app.route('/youtube')
    def youtube_list():
        page = request.args.get('page', 1, type=int)
        videos = YouTubeVideo.query.filter_by(published=True).order_by(YouTubeVideo.created_at.desc()).paginate(page=page, per_page=app.config['VIDEOS_PER_PAGE'], error_out=False)
        return render_template('youtube.html', videos=videos)

    @app.route('/youtube/<video_id>')
    def video_detail(video_id):
        video = YouTubeVideo.query.filter_by(video_id=video_id).first()
        if not video or not video.published:
            abort(404)
        return render_template('video_detail.html', video=video)

    @app.route('/podcast')
    def podcast_list():
        page = request.args.get('page', 1, type=int)
        podcasts = Podcast.query.filter_by(published=True).order_by(Podcast.created_at.desc()).paginate(page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
        return render_template('podcast.html', podcasts=podcasts)

    @app.route('/podcast/<int:id>')
    def podcast_detail(id):
        podcast = Podcast.query.get(id)
        if not podcast or not podcast.published:
            abort(404)
        podcast.views = (podcast.views or 0) + 1
        db.session.commit()
        return render_template('podcast_detail.html', podcast=podcast)

    @app.route('/shorts')
    def shorts_list():
        page = request.args.get('page', 1, type=int)
        shorts = Short.query.filter_by(published=True).order_by(Short.created_at.desc()).paginate(page=page, per_page=app.config['SHORTS_PER_PAGE'], error_out=False)
        return render_template('shorts.html', shorts=shorts)

    @app.route('/shorts/<video_id>')
    def short_detail(video_id):
        short = Short.query.filter_by(video_id=video_id).first()
        if not short or not short.published:
            abort(404)
        return render_template('short_detail.html', short=short)

    @app.route('/community')
    def community_list():
        page = request.args.get('page', 1, type=int)
        posts = CommunityPost.query.filter_by(published=True).order_by(CommunityPost.created_at.desc()).paginate(page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
        return render_template('community.html', posts=posts)
    
    @app.route('/about')
    def about():
        return render_template('about.html')
        
    @app.route('/submit-idea', methods=['GET', 'POST'])
    def submit_idea():
        if request.method == 'POST':
            idea = TopicIdea(
                topic=request.form.get('topic'),
                description=request.form.get('description'),
                email=request.form.get('email'),
                name=request.form.get('name')
            )
            db.session.add(idea)
            db.session.commit()
            flash('Idea submitted!', 'success')
            return redirect(url_for('submit_idea'))
        return render_template('submit_idea.html')

    # ========== AUTH ROUTES ==========
    
    @app.route('/admin/login', methods=['GET', 'POST'])
    def admin_login():
        if current_user.is_authenticated:
            return redirect(url_for('admin_dashboard'))
        if request.method == 'POST':
            user = User.query.filter_by(username=request.form.get('username')).first()
            if user and user.check_password(request.form.get('password')):
                login_user(user)
                return redirect(url_for('admin_dashboard'))
            flash('Invalid credentials.', 'error')
        return render_template('admin/login.html')

    @app.route('/admin/logout')
    @login_required
    def admin_logout():
        logout_user()
        return redirect(url_for('index'))
    
    @app.route('/admin/signup', methods=['GET', 'POST'])
    def admin_signup():
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            
            # Check if username exists
            if User.query.filter_by(username=username).first():
                flash('Username already exists. Please choose another.', 'error')
            # Check if email exists
            elif User.query.filter_by(email=email).first():
                flash('An account with this email already exists.', 'error')
            else:
                user = User(
                    username=username,
                    email=email
                )
                user.set_password(request.form.get('password'))
                db.session.add(user)
                
                try:
                    db.session.commit()
                    
                    # Initialize gamification for new user
                    init_user_gamification(user.id)
                    
                    login_user(user)
                    flash('Account created! Your gamification dashboard is ready.', 'success')
                    return redirect(url_for('admin_dashboard'))
                except Exception as e:
                    db.session.rollback()
                    flash(f'An error occurred: {str(e)}', 'error')
                    
        return render_template('admin/signup.html')

    # ========== MAIN DASHBOARD ==========
    
    @app.route('/admin')
    @admin_required
    def admin_dashboard():
        # Auto-sync YouTube data on refresh (has internal cooldown)
        sync_youtube_data(current_user.id)
        
        stats = get_user_stats()
        weekly = get_weekly_stats()
        
        # Get tasks that are due today based on their schedule
        all_tasks = UserDailyTask.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).order_by(UserDailyTask.is_pinned.desc(), UserDailyTask.display_order).all()
        
        # Filter to only tasks due today
        daily_tasks = [t for t in all_tasks if t.is_due_today()]
        
        # Get pinned trackables
        pinned_trackables = TrackableType.query.filter_by(
            user_id=current_user.id,
            is_active=True,
            is_pinned=True
        ).order_by(TrackableType.display_order).all()
        
        # Recent entries
        recent_entries = TrackableEntry.query.filter_by(
            user_id=current_user.id
        ).order_by(TrackableEntry.created_at.desc()).limit(10).all()
        
        # Get achievements
        unlocked_achievements = UserAchievement.query.filter_by(
            user_id=current_user.id
        ).all()

        # Get dashboard images
        dashboard_images = DashboardImage.query.filter_by(
            user_id=current_user.id
        ).order_by(DashboardImage.created_at.desc()).all()

        # Check usage for confetti
        settings = UserSettings.query.filter_by(user_id=current_user.id).first()
        show_confetti = False
        if (current_user.rank_changed_at == date.today()) or (settings and settings.always_show_confetti):
             show_confetti = True
        
        return render_template('admin/dashboard.html', 
            stats=stats,
            weekly=weekly,
            daily_tasks=daily_tasks,
            pinned_trackables=pinned_trackables,
            recent_entries=recent_entries,
            unlocked_achievements=unlocked_achievements,
            dashboard_images=dashboard_images,
            show_confetti=show_confetti
        )

    # ========== DASHBOARD CUSTOMIZATION ==========

    @app.route('/admin/dashboard/upload_image', methods=['POST'])
    @admin_required
    def upload_dashboard_image():
        if 'image' not in request.files:
            flash('No file part', 'error')
            return redirect(url_for('admin_dashboard'))
            
        file = request.files['image']
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(url_for('admin_dashboard'))
            
        if file:
            filename = secure_filename(file.filename)
            # Ensure unique filename
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            filename = f"{timestamp}_{filename}"
            
            # Save file using absolute path from config
            upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'dashboard')
            os.makedirs(upload_folder, exist_ok=True)
            
            file.save(os.path.join(upload_folder, filename))
            
            # Create DB record - relative URL for frontend
            image_url = url_for('static', filename=f'uploads/dashboard/{filename}')
            dashboard_image = DashboardImage(
                user_id=current_user.id,
                image_url=image_url
            )
            db.session.add(dashboard_image)
            db.session.commit()
            
            flash('Image uploaded successfully', 'success')
            
        return redirect(url_for('admin_dashboard'))

    @app.route('/admin/dashboard/delete_image/<int:image_id>', methods=['POST'])
    @admin_required
    def delete_dashboard_image(image_id):
        image = DashboardImage.query.get_or_404(image_id)
        if image.user_id != current_user.id:
            abort(403)
            
        # Delete from DB
        db.session.delete(image)
        db.session.commit()
        
        # Optional: Delete file from filesystem
        try:
            # Extract filename from URL (simplified assuming standard structure)
            filename = image.image_url.split('/')[-1]
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'dashboard', filename)
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            print(f"Error deleting file: {e}")
        
        flash('Image removed from dashboard', 'success')
        return redirect(url_for('admin_dashboard'))

    @app.route('/admin/dashboard/toggle_header', methods=['POST'])
    @admin_required
    def toggle_dashboard_header():
        settings = UserSettings.query.filter_by(user_id=current_user.id).first()
        if settings:
            settings.show_dashboard_header = not settings.show_dashboard_header
            db.session.commit()
            status = "shown" if settings.show_dashboard_header else "hidden"
            flash(f'Header section {status}', 'success')
        
        return redirect(url_for('admin_dashboard'))

    @app.route('/admin/dashboard/toggle_confetti', methods=['POST'])
    @admin_required
    def toggle_confetti():
        settings = UserSettings.query.filter_by(user_id=current_user.id).first()
        if settings:
            settings.always_show_confetti = not settings.always_show_confetti
            db.session.commit()
            status = "enabled" if settings.always_show_confetti else "disabled"
            flash(f'Always show confetti {status}', 'success')
        
        return redirect(url_for('admin_dashboard', _anchor='settings' if request.form.get('source') == 'settings' else None))


    # ========== TRACKABLE TYPES MANAGEMENT ==========
    
    @app.route('/admin/trackables')
    @admin_required
    def admin_trackables():
        trackables = TrackableType.query.filter_by(
            user_id=current_user.id
        ).order_by(TrackableType.display_order).all()
        return render_template('admin/trackables.html', trackables=trackables)
    
    @app.route('/admin/trackables/add', methods=['GET', 'POST'])
    @admin_required
    def admin_trackable_add():
        if request.method == 'POST':
            name = request.form.get('name')
            trackable = TrackableType(
            user_id=current_user.id,
            name=name,
                slug=name.lower().replace(' ', '_').replace('-', '_'),
                description=request.form.get('description'),
                category=request.form.get('category', 'content'),
                xp_per_unit=int(request.form.get('xp_per_unit', 10)),
                xp_mode=request.form.get('xp_mode', 'fixed'),
                xp_multiplier=float(request.form.get('xp_multiplier', 1.0)),
            icon=request.form.get('icon', 'ph-star'),
                color=request.form.get('color', '#0ea5e9'),
                track_value=request.form.get('track_value') == 'on',
                value_label=request.form.get('value_label', 'Value'),
                value_prefix=request.form.get('value_prefix', '$'),
                daily_goal=int(request.form.get('daily_goal', 0)),
                weekly_goal=int(request.form.get('weekly_goal', 0)),
                monthly_goal=int(request.form.get('monthly_goal', 0)),
                is_pinned=request.form.get('is_pinned') == 'on',
                expense_threshold=float(request.form.get('expense_threshold', 0)) if request.form.get('expense_threshold') else 0
            )
            db.session.add(trackable)
            db.session.commit()
            flash(f'Trackable "{name}" created!', 'success')
            return redirect(url_for('admin_trackables'))
        return render_template('admin/trackable_form.html')
    
    @app.route('/admin/trackables/<int:id>/edit', methods=['GET', 'POST'])
    @admin_required
    def admin_trackable_edit(id):
        trackable = TrackableType.query.get_or_404(id)
        if trackable.user_id != current_user.id:
            abort(403)
        
        if request.method == 'POST':
            trackable.name = request.form.get('name')
            trackable.slug = trackable.name.lower().replace(' ', '_').replace('-', '_')
            trackable.description = request.form.get('description')
            trackable.category = request.form.get('category', 'content')
            trackable.xp_per_unit = int(request.form.get('xp_per_unit', 10))
            trackable.xp_mode = request.form.get('xp_mode', 'fixed')
            trackable.xp_multiplier = float(request.form.get('xp_multiplier', 1.0))
            trackable.icon = request.form.get('icon', 'ph-star')
            trackable.color = request.form.get('color', '#0ea5e9')
            trackable.track_value = request.form.get('track_value') == 'on'
            trackable.value_label = request.form.get('value_label', 'Value')
            trackable.value_prefix = request.form.get('value_prefix', '$')
            trackable.daily_goal = int(request.form.get('daily_goal', 0))
            trackable.weekly_goal = int(request.form.get('weekly_goal', 0))
            trackable.monthly_goal = int(request.form.get('monthly_goal', 0))
            trackable.is_pinned = request.form.get('is_pinned') == 'on'
            trackable.expense_threshold = float(request.form.get('expense_threshold', 0)) if request.form.get('expense_threshold') else 0
            trackable.is_active = request.form.get('is_active') == 'on'
            db.session.commit()
            flash('Trackable updated!', 'success')
            return redirect(url_for('admin_trackables'))
        
        return render_template('admin/trackable_form.html', trackable=trackable)
    
    @app.route('/admin/trackables/<int:id>/delete', methods=['POST'])
    @admin_required
    def admin_trackable_delete(id):
        trackable = TrackableType.query.get_or_404(id)
        if trackable.user_id != current_user.id:
            abort(403)
        db.session.delete(trackable)
        db.session.commit()
        flash('Trackable deleted!', 'success')
        return redirect(url_for('admin_trackables'))

    # ========== TRACKABLE ENTRIES ==========
    
    @app.route('/admin/log', methods=['GET', 'POST'])
    @admin_required
    def admin_log_entry():
        """Quick log entry page"""
        # Find potential bucket conditions for next rank
        stats = get_user_stats()
        next_rank = stats['next_rank']
        buckets = []
        if next_rank:
            # Custom XP/Count types and any condition explicitly marked as a bucket
            buckets = [c for c in next_rank.conditions if c.is_bucket or c.condition_type in ['custom_xp', 'custom_count']]

        if request.method == 'POST':
            trackable_id = int(request.form.get('trackable_id'))
            entry = TrackableEntry(
                user_id=current_user.id,
                trackable_type_id=trackable_id,
                date=datetime.strptime(request.form.get('date', str(date.today())), '%Y-%m-%d').date(),
                count=int(request.form.get('count', 1)),
                value=float(request.form.get('value', 0)) if request.form.get('value') else 0,
                title=request.form.get('title'),
                notes=request.form.get('notes'),
                url=request.form.get('url'),
                allocated_condition_id=request.form.get('allocated_condition_id') or None
            )
            db.session.add(entry)
            
            # Update streak
            streak = Streak.query.filter_by(
                user_id=current_user.id,
                streak_type='daily_xp'
            ).first()
            
            if not streak:
                streak = Streak(
                    user_id=current_user.id,
                    streak_type='daily_xp',
                    current_count=0,
                    longest_count=0
                )
                db.session.add(streak)
                
            streak.update_streak(entry.date)
            
            db.session.commit()
            
            trackable = TrackableType.query.get(trackable_id)
            flash(f'+{entry.get_xp()} XP for {trackable.name}!', 'success')
            return redirect(url_for('admin_dashboard'))

        return render_template('admin/log_entry.html', 
                               trackables=stats['trackables'], 
                               buckets=buckets,
                               next_rank=next_rank,
                               selected_trackable_id=request.args.get('trackable', type=int),
                               today=date.today())
    
    @app.route('/admin/quick-log/<int:trackable_id>', methods=['POST'])
    @admin_required
    def admin_quick_log(trackable_id):
        """Quick log +1 for a trackable"""
        trackable = TrackableType.query.get_or_404(trackable_id)
        if trackable.user_id != current_user.id:
            abort(403)
            
        # If user has manual buckets for next rank, redirect to full log to ask for allocation
        stats = get_user_stats()
        next_rank = stats['next_rank']
        if next_rank and any(c.is_bucket for c in next_rank.conditions):
            return redirect(url_for('admin_log_entry', trackable=trackable.id))
        
        value = float(request.form.get('value', 0))
        entry = TrackableEntry(
            user_id=current_user.id,
            trackable_type_id=trackable_id,
            date=date.today(),
            count=1,
            value=value
        )
        db.session.add(entry)
        
        # Update streak
        streak = Streak.query.filter_by(
            user_id=current_user.id,
            streak_type='daily_xp'
        ).first()
        
        if not streak:
            streak = Streak(
                user_id=current_user.id,
                streak_type='daily_xp',
                current_count=0,
                longest_count=0
            )
            db.session.add(streak)
            
        streak.update_streak(date.today())
            
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'xp': entry.get_xp(),
                'total_count': trackable.get_total_count(),
                'total_xp': trackable.get_total_xp()
            })
        
        flash(f'+{entry.get_xp()} XP!', 'success')
        return redirect(url_for('admin_dashboard'))

    # ========== DAILY TASKS ==========
    
    @app.route('/admin/daily-tasks')
    @admin_required
    def admin_daily_tasks():
        tasks = UserDailyTask.query.filter_by(
            user_id=current_user.id
        ).order_by(UserDailyTask.display_order).all()
        return render_template('admin/daily_tasks.html', tasks=tasks)
    
    @app.route('/admin/daily-tasks/add', methods=['GET', 'POST'])
    @admin_required
    def admin_daily_task_add():
        if request.method == 'POST':
            name = request.form.get('name')
            repeat_type = request.form.get('repeat_type', 'daily')
            
            task = UserDailyTask(
                user_id=current_user.id,
                name=name,
                slug=name.lower().replace(' ', '_'),
                description=request.form.get('description'),
                category=request.form.get('category', 'general'),
                task_type=request.form.get('task_type', 'normal'),
                target_count=int(request.form.get('target_count', 1)),
                repeat_type=repeat_type,
                repeat_interval=int(request.form.get('repeat_interval', 1)),
                repeat_unit=request.form.get('repeat_unit', 'day'),
                repeat_days=request.form.get('repeat_days', '[]'),
                repeat_day_of_month=int(request.form.get('repeat_day_of_month', 1)) if request.form.get('repeat_day_of_month') else None,
                xp_value=int(request.form.get('xp_value', 10)),
                xp_per_count=int(request.form.get('xp_per_count', 0)),
                streak_bonus=request.form.get('streak_bonus') == 'on',
                icon=request.form.get('icon', 'ph-check-circle'),
                color=request.form.get('color', '#10b981'),
                emoji=request.form.get('emoji') or None
            )
            
            # Handle due date for one-time tasks
            if repeat_type == 'once' and request.form.get('due_date'):
                task.due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()
            
            # Initialize ebbinghaus next_due_date
            if repeat_type == 'ebbinghaus':
                task.next_due_date = date.today()
            
            db.session.add(task)
            db.session.commit()
            flash(f'Task "{name}" created!', 'success')
            return redirect(url_for('admin_daily_tasks'))
        return render_template('admin/daily_task_form.html')
    
    @app.route('/admin/daily-tasks/<int:id>/edit', methods=['GET', 'POST'])
    @admin_required
    def admin_daily_task_edit(id):
        task = UserDailyTask.query.get_or_404(id)
        if task.user_id != current_user.id:
            abort(403)
        
        if request.method == 'POST':
            repeat_type = request.form.get('repeat_type', 'daily')
            
            task.name = request.form.get('name')
            task.slug = task.name.lower().replace(' ', '_')
            task.description = request.form.get('description')
            task.category = request.form.get('category', 'general')
            task.task_type = request.form.get('task_type', 'normal')
            task.target_count = int(request.form.get('target_count', 1))
            task.repeat_type = repeat_type
            task.repeat_interval = int(request.form.get('repeat_interval', 1))
            task.repeat_unit = request.form.get('repeat_unit', 'day')
            task.repeat_days = request.form.get('repeat_days', '[]')
            task.repeat_day_of_month = int(request.form.get('repeat_day_of_month', 1)) if request.form.get('repeat_day_of_month') else None
            task.xp_value = int(request.form.get('xp_value', 10))
            task.xp_per_count = int(request.form.get('xp_per_count', 0))
            task.streak_bonus = request.form.get('streak_bonus') == 'on'
            task.icon = request.form.get('icon', 'ph-check-circle')
            task.color = request.form.get('color', '#10b981')
            task.emoji = request.form.get('emoji') or None
            task.is_active = request.form.get('is_active') == 'on'
            task.is_pinned = request.form.get('is_pinned') == 'on'
            
            # Handle due date for one-time tasks
            if repeat_type == 'once' and request.form.get('due_date'):
                task.due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()
            
            db.session.commit()
            flash('Task updated!', 'success')
            return redirect(url_for('admin_daily_tasks'))
        
        return render_template('admin/daily_task_form.html', task=task)
    
    @app.route('/admin/daily-tasks/<int:id>/delete', methods=['POST'])
    @admin_required
    def admin_daily_task_delete(id):
        task = UserDailyTask.query.get_or_404(id)
        if task.user_id != current_user.id:
            abort(403)
        db.session.delete(task)
        db.session.commit()
        flash('Daily task deleted!', 'success')
        return redirect(url_for('admin_daily_tasks'))
    
    @app.route('/admin/daily-tasks/toggle/<slug>', methods=['POST'])
    @admin_required
    def admin_toggle_daily_task(slug):
        """Toggle a daily task completion or add count for count tasks"""
        task = UserDailyTask.query.filter_by(
            user_id=current_user.id,
            slug=slug
        ).first_or_404()
        
        action = request.form.get('action', 'increment')
        today = date.today()
        is_completed = False

        # Handle allocated condition (buckets)
        allocated_condition_id = request.form.get('allocated_condition_id')
        if allocated_condition_id:
            allocated_condition_id = int(allocated_condition_id)

        # Check for ambiguous allocation if adding XP
        should_check_allocation = False
        if action == 'increment':
            should_check_allocation = True
        elif task.task_type == 'normal' and action == 'toggle':
            existing = TaskCompletion.query.filter_by(
                user_id=current_user.id,
                task_id=task.id,
                date=today
            ).first()
            if not existing:
                should_check_allocation = True
        
        if should_check_allocation and not allocated_condition_id:
            stats = get_user_stats()
            next_rank = stats['next_rank']
            if next_rank:
                 # Check for multiple Total XP conditions
                 candidates = [c for c in next_rank.conditions if c.condition_type == 'total_xp']
                 
                 if len(candidates) >= 2:
                     if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                         return jsonify({
                             'success': False,
                             'status': 'ambiguous',
                             'message': 'Select where to add XP',
                             'conditions': [{'id': c.id, 'name': c.custom_name or 'Total XP'} for c in candidates]
                         })
        
        if task.task_type == 'count':
            current_count = task.get_today_completion_count(today)
            
            if action == 'decrement':
                if current_count > 0:
                    # Remove the last completion for today
                    last_completion = TaskCompletion.query.filter_by(
                        user_id=current_user.id,
                        task_id=task.id,
                        date=today
                    ).order_by(TaskCompletion.id.desc()).first()
                    if last_completion:
                        db.session.delete(last_completion)
            else:
                # Increment
                if current_count < task.target_count:
                    # Add a completion
                    completion = TaskCompletion(
                        user_id=current_user.id,
                        task_id=task.id,
                        date=today,
                        count=1,
                        allocated_condition_id=allocated_condition_id
                    )
                    
                    # Calculate XP
                    xp_e = 0
                    if task.xp_per_count > 0:
                        xp_e = task.xp_per_count
                    elif current_count + 1 >= task.target_count:
                        xp_e = task.xp_value
                    
                    completion.xp_earned = xp_e
                    db.session.add(completion)
                
            is_completed = task.is_completed_today(today)
        else:
            # Normal task - toggle completion
            existing = TaskCompletion.query.filter_by(
                user_id=current_user.id,
                task_id=task.id,
                date=today
            ).first()
            
            if existing:
                xp_earned = -existing.xp_earned
                db.session.delete(existing)
                is_completed = False
            else:
                completion = TaskCompletion(
                    user_id=current_user.id,
                    task_id=task.id,
                    date=today,
                    xp_earned=task.xp_value,
                    allocated_condition_id=allocated_condition_id
                )
                xp_earned = task.xp_value
                db.session.add(completion)
                is_completed = True
                
                # Handle ebbinghaus tasks
                if task.repeat_type == 'ebbinghaus':
                    task.calculate_next_ebbinghaus_date()
                
                # Mark one-time and 'none' tasks as completed/archived
                if task.repeat_type in ('once', 'none'):
                    task.completed_date = today
        
        # Update daily log for backward compatibility
        today_log = DailyLog.query.filter_by(
            user_id=current_user.id,
            date=today
        ).first()
        
        if not today_log:
            today_log = DailyLog(user_id=current_user.id, date=today)
            db.session.add(today_log)
        
        # Calculate total XP from TaskCompletions for today
        total_task_xp = db.session.query(db.func.sum(TaskCompletion.xp_earned)).filter(
            TaskCompletion.user_id == current_user.id,
            TaskCompletion.date == today
        ).scalar() or 0
        
        today_log.total_xp = total_task_xp
        
        # Update completed tasks list for backward compatibility
        completed_slugs = []
        completed_tasks = TaskCompletion.query.filter_by(
            user_id=current_user.id,
            date=today
        ).all()
        for tc in completed_tasks:
            if tc.task and tc.task.is_completed_today(today):
                completed_slugs.append(tc.task.slug)
        today_log.set_completed_tasks(list(set(completed_slugs)))
        
        # Check if goal met
        settings = UserSettings.query.filter_by(user_id=current_user.id).first()
        if settings and today_log.total_xp >= settings.daily_xp_goal:
            today_log.goal_met = True
            
        # Update streak if any tasks are completed
        if completed_tasks:
            streak = Streak.query.filter_by(
                user_id=current_user.id,
                streak_type='daily_xp'
            ).first()
            
            if not streak:
                streak = Streak(
                    user_id=current_user.id,
                    streak_type='daily_xp',
                    current_count=0,
                    longest_count=0
                )
                db.session.add(streak)
                
            streak.update_streak(today)
        
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'completed': is_completed,
                'total_xp': today_log.total_xp,
                'count': task.get_today_completion_count() if task.task_type == 'count' else None,
                'target': task.target_count if task.task_type == 'count' else None,
                'goal_met': today_log.goal_met
            })
        
        return redirect(url_for('admin_dashboard'))

    # ========== RANKS MANAGEMENT ==========
    
    @app.route('/admin/ranks')
    @admin_required
    def admin_ranks():
        ranks = CustomRank.query.filter_by(
            user_id=current_user.id
        ).order_by(CustomRank.level).all()
        return render_template('admin/ranks.html', ranks=ranks)
    
    @app.route('/admin/ranks/add', methods=['GET', 'POST'])
    @admin_required
    def admin_rank_add():
        if request.method == 'POST':
            rank = CustomRank(
                user_id=current_user.id,
                level=int(request.form.get('level', 1)),
                name=request.form.get('name'),
                code=request.form.get('code'),
                description=request.form.get('description'),
                min_xp=int(request.form.get('min_xp')) if request.form.get('min_xp') else None,
                color=request.form.get('color', '#666666'),
                icon=request.form.get('icon'),
                is_max_rank=request.form.get('is_max_rank') == 'on'
            )
            db.session.add(rank)
            db.session.flush()  # Get rank.id before adding conditions
            
            # Handle conditions from JSON
            conditions_json = request.form.get('conditions_json', '[]')
            try:
                conditions_data = json.loads(conditions_json)
                for cond in conditions_data:
                    condition = RankCondition(
                        rank_id=rank.id,
                        condition_type=cond['type'],
                        threshold=int(cond['threshold']),
                        trackable_slug=cond.get('trackable_slug'),
                        custom_name=cond.get('custom_name'),
                        # Auto-set is_bucket for custom types
                        is_bucket=cond.get('is_bucket', False) or cond['type'] in ['custom_xp', 'custom_count']
                    )
                    db.session.add(condition)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                db.session.rollback()
                flash(f'Error processing conditions: {str(e)}', 'error')
                return redirect(url_for('admin_rank_add'))
            
            db.session.commit()
            flash(f'Rank "{rank.name}" created!', 'success')
            return redirect(url_for('admin_ranks'))
        
        # Get trackables for condition selector
        trackables = TrackableType.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).order_by(TrackableType.name).all()

        # Get existing condition names for pooling/carry-over
        existing_conditions = db.session.query(RankCondition.custom_name)\
            .join(CustomRank)\
            .filter(CustomRank.user_id == current_user.id)\
            .filter(RankCondition.custom_name != None)\
            .distinct().all()
        existing_condition_names = [c[0] for c in existing_conditions if c[0]]
        
        return render_template('admin/rank_form.html', 
                             trackables=trackables, 
                             existing_condition_names=existing_condition_names)
    
    @app.route('/admin/ranks/<int:id>/edit', methods=['GET', 'POST'])
    @admin_required
    def admin_rank_edit(id):
        rank = CustomRank.query.get_or_404(id)
        if rank.user_id != current_user.id:
            abort(403)
        
        if request.method == 'POST':
            rank.level = int(request.form.get('level', 1))
            rank.name = request.form.get('name')
            rank.code = request.form.get('code')
            rank.description = request.form.get('description')
            rank.min_xp = int(request.form.get('min_xp')) if request.form.get('min_xp') else None
            rank.color = request.form.get('color', '#666666')
            rank.icon = request.form.get('icon')
            rank.is_max_rank = request.form.get('is_max_rank') == 'on'
            
            # Delete existing conditions
            RankCondition.query.filter_by(rank_id=rank.id).delete()
            
            # Add new conditions from JSON
            conditions_json = request.form.get('conditions_json', '[]')
            try:
                conditions_data = json.loads(conditions_json)
                for cond in conditions_data:
                    condition = RankCondition(
                        rank_id=rank.id,
                        condition_type=cond['type'],
                        threshold=int(cond['threshold']),
                        trackable_slug=cond.get('trackable_slug'),
                        custom_name=cond.get('custom_name'),
                        # Auto-set is_bucket for custom types
                        is_bucket=cond.get('is_bucket', False) or cond['type'] in ['custom_xp', 'custom_count']
                    )
                    db.session.add(condition)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                db.session.rollback()
                flash(f'Error processing conditions: {str(e)}', 'error')
                return redirect(url_for('admin_rank_edit', id=id))
            
            db.session.commit()
            flash('Rank updated!', 'success')
            return redirect(url_for('admin_ranks'))
        
        # Get trackables for condition selector
        trackables = TrackableType.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).order_by(TrackableType.name).all()

        # Get existing condition names for pooling/carry-over
        existing_conditions = db.session.query(RankCondition.custom_name)\
            .join(CustomRank)\
            .filter(CustomRank.user_id == current_user.id)\
            .filter(RankCondition.custom_name != None)\
            .distinct().all()
        existing_condition_names = [c[0] for c in existing_conditions if c[0]]
        
        return render_template('admin/rank_form.html', 
                             rank=rank, 
                             trackables=trackables, 
                             existing_condition_names=existing_condition_names)
    
    @app.route('/admin/ranks/<int:id>/delete', methods=['POST'])
    @admin_required
    def admin_rank_delete(id):
        rank = CustomRank.query.get_or_404(id)
        if rank.user_id != current_user.id:
            abort(403)
        db.session.delete(rank)
        db.session.commit()
        flash('Rank deleted!', 'success')
        return redirect(url_for('admin_ranks'))
    
    @app.route('/api/condition-preview')
    @admin_required
    def api_condition_preview():
        """Get current values for all condition types for preview"""
        stats = get_user_stats()
        
        # Get YouTube data
        youtube_long_count = YouTubeVideo.query.filter_by(user_id=current_user.id).count()
        youtube_short_count = Short.query.filter_by(user_id=current_user.id).count()
        total_videos_count = YouTubeVideo.query.filter_by(user_id=current_user.id).count() + Short.query.filter_by(user_id=current_user.id).count()
        
        from sqlalchemy import func
        youtube_long_views = db.session.query(func.sum(YouTubeVideo.views)).filter_by(user_id=current_user.id).scalar() or 0
        youtube_short_views = db.session.query(func.sum(Short.views)).filter_by(user_id=current_user.id).scalar() or 0
        
        # Get trackable data
        trackables = TrackableType.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).all()
        
        trackable_data = {}
        for t in trackables:
            trackable_data[t.slug] = {
                'name': t.name,
                'xp': t.get_total_xp(),
                'count': t.get_total_count()
            }
        
        return jsonify({
            'total_xp': stats['total_xp'] if stats else 0,
            'streak_current': stats['streak'].current_count if stats and stats['streak'] else 0,
            'streak_longest': stats['streak'].longest_count if stats and stats['streak'] else 0,
            'tasks_completed': TaskCompletion.query.filter_by(user_id=current_user.id).count(),
            'achievements_unlocked': UserAchievement.query.filter_by(user_id=current_user.id).count(),
            'youtube_long_count': youtube_long_count,
            'youtube_short_count': youtube_short_count,
            'youtube_long_views': youtube_long_views,
            'youtube_short_views': youtube_short_views,
            'youtube_total_views': youtube_long_views + youtube_short_views,
            'total_videos_count': total_videos_count,
            'trackables': trackable_data
        })

    # ========== ACHIEVEMENTS ==========
    
    @app.route('/admin/achievements')
    @admin_required
    def admin_achievements():
        achievements = Achievement.query.filter_by(
            user_id=current_user.id
        ).all()
        unlocked = {ua.achievement_id for ua in UserAchievement.query.filter_by(user_id=current_user.id).all()}
        return render_template('admin/achievements.html', achievements=achievements, unlocked=unlocked)
    
    @app.route('/admin/achievements/add', methods=['GET', 'POST'])
    @admin_required
    def admin_achievement_add():
        if request.method == 'POST':
            name = request.form.get('name')
            criteria = {
                'type': request.form.get('criteria_type', 'xp_total'),
                'threshold': int(request.form.get('threshold', 100))
            }
            if request.form.get('trackable_slug'):
                criteria['trackable_slug'] = request.form.get('trackable_slug')
            
            achievement = Achievement(
                user_id=current_user.id,
                name=name,
                slug=name.lower().replace(' ', '_'),
                description=request.form.get('description'),
                xp_reward=int(request.form.get('xp_reward', 100)),
                icon=request.form.get('icon', 'ph-trophy'),
                color=request.form.get('color', '#fbbf24')
            )
            achievement.set_criteria(criteria)
            db.session.add(achievement)
            db.session.commit()
            flash(f'Achievement "{name}" created!', 'success')
            return redirect(url_for('admin_achievements'))
        
        trackables = TrackableType.query.filter_by(user_id=current_user.id).all()
        return render_template('admin/achievement_form.html', trackables=trackables)

    # ========== SETTINGS ==========
    
    @app.route('/admin/settings', methods=['GET', 'POST'])
    @admin_required
    def admin_settings():
        settings = UserSettings.query.filter_by(user_id=current_user.id).first()
        if not settings:
            settings = UserSettings(user_id=current_user.id)
            db.session.add(settings)
            db.session.commit()
        
        if request.method == 'POST':
            settings.accent_color = request.form.get('accent_color', '#e90e0e')
            settings.points_name = request.form.get('points_name', 'XP')
            settings.points_icon = request.form.get('points_icon', 'ph-lightning')
            settings.daily_xp_goal = int(request.form.get('daily_xp_goal', 50))
            settings.perfect_day_bonus = int(request.form.get('perfect_day_bonus', 50))
            settings.perfect_week_bonus = int(request.form.get('perfect_week_bonus', 500))
            settings.streak_bonus_per_day = int(request.form.get('streak_bonus_per_day', 5))
            settings.show_xp_animations = request.form.get('show_xp_animations') == 'on'
            settings.show_dashboard_header = request.form.get('show_dashboard_header') == 'on'
            settings.enable_youtube_sync = request.form.get('enable_youtube_sync') == 'on'
            settings.always_show_confetti = request.form.get('always_show_confetti') == 'on'
            db.session.commit()
            flash('Settings saved!', 'success')
            return redirect(url_for('admin_settings'))
        
        return render_template('admin/settings.html', settings=settings)

    @app.route('/admin/settings/export')
    @admin_required
    def admin_export_settings():
        """Export all user data to a .cryptasium file"""
        from flask import make_response
        
        # Gather all related data
        user = User.query.get(current_user.id)
        settings = UserSettings.query.filter_by(user_id=current_user.id).first()
        trackables = TrackableType.query.filter_by(user_id=current_user.id).all()
        entries = TrackableEntry.query.filter_by(user_id=current_user.id).all()
        ranks = CustomRank.query.filter_by(user_id=current_user.id).all()
        tasks = UserDailyTask.query.filter_by(user_id=current_user.id).all()
        completions = TaskCompletion.query.filter_by(user_id=current_user.id).all()
        achievements = Achievement.query.filter_by(user_id=current_user.id).all()
        user_achievements = UserAchievement.query.filter_by(user_id=current_user.id).all()
        streaks = Streak.query.filter_by(user_id=current_user.id).all()
        logs = DailyLog.query.filter_by(user_id=current_user.id).all()
        images = DashboardImage.query.filter_by(user_id=current_user.id).all()
        
        data = {
            'version': '2.0',
            'exported_at': datetime.now().isoformat(),
            'username': user.username,
            'user_settings': settings.to_dict() if settings else {},
            'trackable_types': [t.to_dict() for t in trackables],
            'trackable_entries': [e.to_dict() for e in entries],
            'ranks': [],
            'daily_tasks': [t.to_dict() for t in tasks],
            'task_completions': [c.to_dict() for c in completions],
            'achievements': [a.to_dict() for a in achievements],
            'user_achievements': [ua.to_dict() for ua in user_achievements],
            'streaks': [s.to_dict() for s in streaks],
            'daily_logs': [l.to_dict() for l in logs],
            'dashboard_images': [i.to_dict() for i in images]
        }
        
        # Add ranks with their conditions
        for rank in ranks:
            r_dict = rank.to_dict()
            r_dict['conditions'] = [c.to_dict() for c in rank.conditions]
            data['ranks'].append(r_dict)
            
        # Create response
        json_data = json.dumps(data, indent=4)
        response = make_response(json_data)
        
        # Set content type and filename with .cryptasium extension
        filename = f"backup_{current_user.username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.cryptasium"
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        response.headers['Content-Type'] = 'application/json'
        
        return response

    @app.route('/admin/settings/import', methods=['POST'])
    @admin_required
    def admin_import_settings():
        """Import all user data from a .cryptasium file"""
        if 'backup_file' not in request.files:
            flash('No file provided', 'error')
            return redirect(url_for('admin_settings'))
            
        file = request.files['backup_file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('admin_settings'))
            
        try:
            from datetime import date
            # Read and parse JSON
            content = file.read().decode('utf-8')
            data = json.loads(content)
            version = data.get('version', '1.0')
            
            # 1. Update User Settings
            s_data = data.get('user_settings', {})
            if s_data:
                settings = UserSettings.query.filter_by(user_id=current_user.id).first()
                if not settings:
                    settings = UserSettings(user_id=current_user.id)
                    db.session.add(settings)
                for key, value in s_data.items():
                    if hasattr(settings, key) and key not in ['id', 'user_id', 'created_at', 'updated_at']:
                        setattr(settings, key, value)

            # 2. Trackable Types
            t_types_data = data.get('trackable_types', data.get('trackables', [])) # version 1.0 used 'trackables'
            t_type_map = {} # slug -> id
            for t_data in t_types_data:
                slug = t_data.get('slug')
                if not slug: continue
                trackable = TrackableType.query.filter_by(user_id=current_user.id, slug=slug).first()
                if not trackable:
                    trackable = TrackableType(user_id=current_user.id, slug=slug)
                    db.session.add(trackable)
                for key, value in t_data.items():
                    if hasattr(trackable, key) and key not in ['id', 'user_id', 'created_at', 'updated_at', 'total_count', 'total_xp']:
                        setattr(trackable, key, value)
                db.session.flush()
                t_type_map[slug] = trackable.id

            # 3. Daily Tasks
            tasks_data = data.get('daily_tasks', [])
            task_map = {} # slug -> id
            for task_data in tasks_data:
                slug = task_data.get('slug')
                if not slug: continue
                task = UserDailyTask.query.filter_by(user_id=current_user.id, slug=slug).first()
                if not task:
                    task = UserDailyTask(user_id=current_user.id, slug=slug)
                    db.session.add(task)
                for key, value in task_data.items():
                    if hasattr(task, key) and key not in ['id', 'user_id', 'created_at', 'updated_at']:
                        if key in ['due_date', 'completed_date', 'next_due_date'] and value:
                            setattr(task, key, date.fromisoformat(value[:10]))
                        else:
                            setattr(task, key, value)
                db.session.flush()
                task_map[slug] = task.id

            # 4. Ranks & Conditions
            r_list = data.get('ranks', [])
            for r_data in r_list:
                level = r_data.get('level')
                if level is None: continue
                rank = CustomRank.query.filter_by(user_id=current_user.id, level=level).first()
                if not rank:
                    rank = CustomRank(user_id=current_user.id, level=level)
                    db.session.add(rank)
                for key, value in r_data.items():
                    if hasattr(rank, key) and key not in ['id', 'user_id', 'created_at', 'updated_at', 'conditions', 'condition_count']:
                        setattr(rank, key, value)
                db.session.flush()
                # Clear existing and rebuild conditions
                RankCondition.query.filter_by(rank_id=rank.id).delete()
                for c_data in r_data.get('conditions', []):
                    cond = RankCondition(
                        rank_id=rank.id,
                        condition_type=c_data.get('condition_type') or c_data.get('type'),
                        threshold=c_data.get('threshold', 0),
                        custom_name=c_data.get('custom_name'),
                        trackable_slug=c_data.get('trackable_slug'),
                        is_bucket=c_data.get('is_bucket', False)
                    )
                    db.session.add(cond)

            # 5. Achievements
            ach_data = data.get('achievements', [])
            ach_map = {} # slug -> id
            for a_data in ach_data:
                slug = a_data.get('slug')
                if not slug: continue
                achievement = Achievement.query.filter_by(user_id=current_user.id, slug=slug).first()
                if not achievement:
                    achievement = Achievement(user_id=current_user.id, slug=slug)
                    db.session.add(achievement)
                for key, value in a_data.items():
                    if hasattr(achievement, key) and key not in ['id', 'user_id', 'created_at']:
                        setattr(achievement, key, value)
                db.session.flush()
                ach_map[slug] = achievement.id

            # 6. Streaks
            streaks_data = data.get('streaks', [])
            for s_data in streaks_data:
                s_type = s_data.get('streak_type')
                if not s_type: continue
                streak = Streak.query.filter_by(user_id=current_user.id, streak_type=s_type).first()
                if not streak:
                    streak = Streak(user_id=current_user.id, streak_type=s_type)
                    db.session.add(streak)
                for key, value in s_data.items():
                    if hasattr(streak, key) and key not in ['id', 'user_id', 'created_at', 'updated_at']:
                        if key in ['last_activity_date', 'streak_start_date'] and value:
                            setattr(streak, key, date.fromisoformat(value[:10]))
                        else:
                            setattr(streak, key, value)

            # 7. Historical Data (Optional version check or always import)
            # Trackable Entries
            entries_data = data.get('trackable_entries', [])
            for e_data in entries_data:
                slug = e_data.get('trackable_slug')
                if slug not in t_type_map: continue
                
                # Check for existing entry to avoid duplicates (loose check by date/count/value/type)
                # This might be slow if there are thousands, but it's a restore.
                # For simplicity, we just add them unless identical exists.
                entry_date = date.fromisoformat(e_data['date'][:10])
                existing = TrackableEntry.query.filter_by(
                    user_id=current_user.id,
                    trackable_type_id=t_type_map[slug],
                    date=entry_date,
                    count=e_data.get('count'),
                    value=e_data.get('value')
                ).first()
                
                if not existing:
                    entry = TrackableEntry(
                        user_id=current_user.id,
                        trackable_type_id=t_type_map[slug],
                        date=entry_date,
                        count=e_data.get('count', 1),
                        value=e_data.get('value', 0),
                        title=e_data.get('title'),
                        notes=e_data.get('notes'),
                        url=e_data.get('url'),
                        duration_minutes=e_data.get('duration_minutes', 0),
                        views=e_data.get('views', 0),
                        tier_name=e_data.get('tier_name')
                    )
                    db.session.add(entry)

            # Task Completions
            comp_data = data.get('task_completions', [])
            for c_data in comp_data:
                slug = c_data.get('task_slug')
                if slug not in task_map: continue
                comp_date = date.fromisoformat(c_data['date'][:10])
                existing = TaskCompletion.query.filter_by(
                    user_id=current_user.id,
                    task_id=task_map[slug],
                    date=comp_date,
                    xp_earned=c_data.get('xp_earned')
                ).first()
                if not existing:
                    comp = TaskCompletion(
                        user_id=current_user.id,
                        task_id=task_map[slug],
                        date=comp_date,
                        count=c_data.get('count', 1),
                        notes=c_data.get('notes'),
                        xp_earned=c_data.get('xp_earned', 0)
                    )
                    db.session.add(comp)

            # User Achievements
            ua_data = data.get('user_achievements', [])
            for u_data in ua_data:
                slug = u_data.get('achievement_slug')
                if slug not in ach_map: continue
                existing = UserAchievement.query.filter_by(
                    user_id=current_user.id,
                    achievement_id=ach_map[slug]
                ).first()
                if not existing:
                    ua = UserAchievement(
                        user_id=current_user.id,
                        achievement_id=ach_map[slug],
                        unlocked_at=datetime.fromisoformat(u_data['unlocked_at'])
                    )
                    db.session.add(ua)

            # Daily Logs
            logs_data = data.get('daily_logs', [])
            for l_data in logs_data:
                log_date = date.fromisoformat(l_data['date'][:10])
                log = DailyLog.query.filter_by(user_id=current_user.id, date=log_date).first()
                if not log:
                    log = DailyLog(user_id=current_user.id, date=log_date)
                    db.session.add(log)
                for key, value in l_data.items():
                    if hasattr(log, key) and key not in ['id', 'user_id', 'date']:
                        setattr(log, key, value)

            # Dashboard Images
            img_data = data.get('dashboard_images', [])
            for i_data in img_data:
                existing = DashboardImage.query.filter_by(
                    user_id=current_user.id,
                    image_url=i_data['image_url']
                ).first()
                if not existing:
                    img = DashboardImage(
                        user_id=current_user.id,
                        image_url=i_data['image_url'],
                        created_at=datetime.fromisoformat(i_data['created_at'])
                    )
                    db.session.add(img)

            db.session.commit()
            flash('All data imported successfully!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Import failed: {str(e)}', 'error')
            
        return redirect(url_for('admin_settings'))

    @app.route('/admin/reset-password', methods=['POST'])
    @admin_required
    def admin_reset_password():
        """Reset password for the current user"""
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not current_user.check_password(current_password):
            flash('Current password is incorrect.', 'error')
            return redirect(url_for('admin_settings'))
            
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('admin_settings'))
            
        if len(new_password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return redirect(url_for('admin_settings'))
            
        current_user.set_password(new_password)
        db.session.commit()
        
        flash('Password updated successfully!', 'success')
        return redirect(url_for('admin_settings'))

    # ========== PROGRESS PAGE ==========
    
    @app.route('/admin/progress')
    @admin_required
    def admin_progress():
        stats = get_user_stats()
        weekly = get_weekly_stats()
        
        # Get last 365 days of daily logs
        end_date = date.today()
        start_date = end_date - timedelta(days=364) # 365 days total including today
        
        daily_logs = DailyLog.query.filter(
            DailyLog.user_id == current_user.id,
            DailyLog.date >= start_date,
            DailyLog.date <= end_date
        ).all()
        
        # Build calendar data lookup
        logs_by_date = {log.date.isoformat(): log for log in daily_logs}
        
        # Calculate max XP for scaling
        max_xp = 0
        for log in daily_logs:
            if log.total_xp > max_xp:
                max_xp = log.total_xp
        
        # Determine quartiles for activity levels (0-4)
        # Level 0: 0 XP
        # Level 1: 1 - 25% of max
        # Level 2: 25% - 50% of max
        # Level 3: 50% - 75% of max
        # Level 4: 75% - 100% of max
        
        calendar_data = {}
        # Pre-fill all dates
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.isoformat()
            log = logs_by_date.get(date_str)
            
            xp = log.total_xp if log else 0
            level = 0
            
            if xp > 0:
                if max_xp <= 0:
                    level = 1
                else:
                    ratio = xp / max_xp
                    if ratio <= 0.25: level = 1
                    elif ratio <= 0.50: level = 2
                    elif ratio <= 0.75: level = 3
                    else: level = 4
            
            calendar_data[date_str] = {
                'xp': xp,
                'goal_met': log.goal_met if log else False,
                'level': level,
                'date': current_date
            }
            
            current_date += timedelta(days=1)
        
        return render_template('admin/progress.html',
            stats=stats,
            weekly=weekly,
            calendar_data=calendar_data,
            start_date=start_date,
            end_date=end_date,
            timedelta=timedelta,
            daily_logs=daily_logs # Keeping for compatible view below if needed
        )

    # ========== CALENDAR ==========
    
    @app.route('/admin/calendar')
    @admin_required
    def admin_calendar():
        # Get calendar entries
        entries = ContentCalendarEntry.query.filter_by(
            user_id=current_user.id
        ).order_by(ContentCalendarEntry.scheduled_date).all()
        
        trackables = TrackableType.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).all()
        
        # Calculate dates
        today = date.today()
        selected_date_str = request.args.get('date')
        if selected_date_str:
            try:
                selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            except:
                selected_date = today
        else:
            selected_date = today
        
        start_of_week = selected_date - timedelta(days=selected_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        # Build week_days list
        week_days = []
        for i in range(7):
            d = start_of_week + timedelta(days=i)
            day_entries = [e for e in entries if e.scheduled_date == d]
            week_days.append({
                'date': d,
                'is_today': d == today,
                'entries': day_entries
            })
        
        # Build month calendar
        month_start = selected_date.replace(day=1)
        first_calendar_day = month_start - timedelta(days=month_start.weekday())
        month_days = []
        for i in range(42):
            d = first_calendar_day + timedelta(days=i)
            day_entries = [e for e in entries if e.scheduled_date == d]
            month_days.append({
                'date': d,
                'is_today': d == today,
                'is_other_month': d.month != selected_date.month,
                'entries': day_entries
            })
        
        # Entries for selected date
        selected_entries = [e for e in entries if e.scheduled_date == selected_date]
        
        # Build posting schedule from trackables
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        posting_schedule = []
        for i, t in enumerate(trackables):
            if t.weekly_goal > 0:
                day_idx = i % 7
                posting_schedule.append({
                    'content_type': t.slug,
                    'content_label': t.name,
                    'color': t.color,
                    'icon': t.icon,
                    'day_of_week': day_idx,
                    'day_name': day_names[day_idx],
                    'preferred_time': '',
                    'required': t.weekly_goal
                })
        
        return render_template('admin/calendar.html', 
            entries=entries, 
            trackables=trackables,
            today=today,
            selected_date=selected_date,
            start_of_week=start_of_week,
            end_of_week=end_of_week,
            week_days=week_days,
            month_days=month_days,
            selected_entries=selected_entries,
            posting_schedule=posting_schedule
        )

    # ========== LEGACY CONTENT MANAGEMENT ==========
    
    @app.route('/admin/blog')
    @admin_required
    def admin_blog_list():
        posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
        return render_template('admin/blog_list.html', posts=posts)
        
    @app.route('/admin/blog/new', methods=['GET', 'POST'])
    @admin_required
    def admin_blog_new():
        if request.method == 'POST':
            post = BlogPost(
                title=request.form.get('title'),
                slug=request.form.get('slug') or request.form.get('title').lower().replace(' ', '-'),
                excerpt=request.form.get('excerpt'),
                content=request.form.get('content'),
                featured_image=request.form.get('featured_image'),
                author=request.form.get('author'),
                published=request.form.get('published') == 'on',
                user_id=current_user.id
            )
            db.session.add(post)
            db.session.commit()
            return redirect(url_for('admin_blog_list'))
        return render_template('admin/blog_form.html')

    @app.route('/admin/blog/<int:id>/edit', methods=['GET', 'POST'])
    @admin_required
    def admin_blog_edit(id):
        post = BlogPost.query.get_or_404(id)
        if request.method == 'POST':
            post.title = request.form.get('title')
            post.content = request.form.get('content')
            post.published = request.form.get('published') == 'on'
            db.session.commit()
            return redirect(url_for('admin_blog_list'))
        return render_template('admin/blog_form.html', post=post)
        
    @app.route('/admin/blog/<int:id>/delete', methods=['POST'])
    @admin_required
    def admin_blog_delete(id):
        post = BlogPost.query.get_or_404(id)
        db.session.delete(post)
        db.session.commit()
        return redirect(url_for('admin_blog_list'))
    
    @app.route('/admin/youtube')
    @admin_required
    def admin_youtube_list():
        videos = YouTubeVideo.query.order_by(YouTubeVideo.created_at.desc()).all()
        return render_template('admin/youtube_list.html', videos=videos)
        
    @app.route('/admin/youtube/new', methods=['GET', 'POST'])
    @admin_required
    def admin_youtube_new():
        if request.method == 'POST':
            video = YouTubeVideo(
                title=request.form.get('title'),
                video_id=request.form.get('video_id'),
                description=request.form.get('description'),
                published=request.form.get('published') == 'on',
                user_id=current_user.id
            )
            db.session.add(video)
            db.session.commit()
            return redirect(url_for('admin_youtube_list'))
        return render_template('admin/youtube_form.html')
        
    @app.route('/admin/shorts')
    @admin_required
    def admin_shorts_list():
        shorts = Short.query.order_by(Short.created_at.desc()).all()
        return render_template('admin/shorts_list.html', shorts=shorts)

    @app.route('/admin/shorts/new', methods=['GET', 'POST'])
    @admin_required
    def admin_shorts_new():
        if request.method == 'POST':
            short = Short(
                title=request.form.get('title'),
                video_id=request.form.get('video_id'),
                description=request.form.get('description'),
                published=request.form.get('published') == 'on',
                user_id=current_user.id
            )
            db.session.add(short)
            db.session.commit()
            return redirect(url_for('admin_shorts_list'))
        return render_template('admin/shorts_form.html')

    @app.route('/admin/podcast')
    @admin_required
    def admin_podcast_list():
        podcasts = Podcast.query.order_by(Podcast.created_at.desc()).all()
        return render_template('admin/podcast_list.html', podcasts=podcasts)

    @app.route('/admin/podcast/new', methods=['GET', 'POST'])
    @admin_required
    def admin_podcast_new():
        if request.method == 'POST':
            podcast = Podcast(
                title=request.form.get('title'),
                description=request.form.get('description'),
                episode_number=int(request.form.get('episode_number') or 0),
                published=request.form.get('published') == 'on',
                user_id=current_user.id
            )
            db.session.add(podcast)
            db.session.commit()
            return redirect(url_for('admin_podcast_list'))
        return render_template('admin/podcast_form.html')

    @app.route('/admin/community')
    @admin_required
    def admin_community_list():
        posts = CommunityPost.query.order_by(CommunityPost.created_at.desc()).all()
        return render_template('admin/community_list.html', posts=posts)

    @app.route('/admin/ideas')
    @admin_required
    def admin_ideas_list():
        ideas = TopicIdea.query.order_by(TopicIdea.created_at.desc()).all()
        return render_template('admin/ideas_list.html', ideas=ideas)

    # ========== API ENDPOINTS ==========
    
    @app.route('/api/stats')
    @admin_required
    def api_stats():
        stats = get_user_stats()
        return jsonify({
            'total_xp': stats['total_xp'],
            'current_rank': stats['current_rank'].to_dict() if stats['current_rank'] else None,
            'next_rank': stats['next_rank'].to_dict() if stats['next_rank'] else None,
            'progress_percent': stats['progress_percent'],
            'streak': stats['streak'].current_count if stats['streak'] else 0
        })
    
    @app.route('/api/trackables')
    @admin_required
    def api_trackables():
        trackables = TrackableType.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).order_by(TrackableType.display_order).all()
        return jsonify([t.to_dict() for t in trackables])

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
