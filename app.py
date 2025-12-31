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
    SystemSettings, User, TrackableType, TrackableEntry, CustomRank,
    UserDailyTask, TaskCompletion, DailyLog, Achievement, UserAchievement, Streak,
    UserSettings, ContentCalendarEntry, init_user_gamification
)
import youtube_service
from flask_login import LoginManager, login_user, logout_user, login_required, current_user


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
    
    # ========== DECORATORS ==========
    
    def admin_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('admin_login'))
            return f(*args, **kwargs)
        return decorated_function
    
    # ========== HELPER FUNCTIONS ==========
    
    def get_user_stats():
        """Get comprehensive stats for the current user"""
        if not current_user.is_authenticated:
            return None
        
        # Get trackable types and their totals
        trackables = TrackableType.query.filter_by(
            user_id=current_user.id, 
            is_active=True
        ).order_by(TrackableType.display_order).all()
        
        # Calculate total XP
        total_xp = 0
        for t in trackables:
            total_xp += t.get_total_xp()
        
        # Add daily task XP
        daily_logs = DailyLog.query.filter_by(user_id=current_user.id).all()
        for log in daily_logs:
            total_xp += log.total_xp or 0
        
        # Get current rank
        ranks = CustomRank.query.filter_by(
            user_id=current_user.id
        ).order_by(CustomRank.min_xp.desc()).all()
        
        current_rank = None
        next_rank = None
        
        for i, rank in enumerate(ranks):
            if total_xp >= rank.min_xp:
                current_rank = rank
                break
        
        # Find next rank
        if current_rank:
            for rank in reversed(ranks):
                if rank.min_xp > current_rank.min_xp:
                    next_rank = rank
                    break
        elif ranks:
            next_rank = ranks[-1]  # Lowest rank
        
        # Calculate progress
        progress_percent = 0
        if current_rank and next_rank:
            xp_in_rank = total_xp - current_rank.min_xp
            xp_needed = next_rank.min_xp - current_rank.min_xp
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
        
        return {
            'total_xp': total_xp,
            'trackables': trackables,
            'current_rank': current_rank,
            'next_rank': next_rank,
            'progress_percent': progress_percent,
            'ranks': list(reversed(ranks)),
            'streak': streak,
            'settings': settings,
            'today_log': today_log
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
            if User.query.filter_by(username=request.form.get('username')).first():
                flash('Username exists', 'error')
            else:
                user = User(
                    username=request.form.get('username'),
                    email=request.form.get('email')
                )
                user.set_password(request.form.get('password'))
                db.session.add(user)
                db.session.commit()
                
                # Initialize gamification for new user
                init_user_gamification(user.id)
                
                login_user(user)
                flash('Account created! Your gamification dashboard is ready.', 'success')
                return redirect(url_for('admin_dashboard'))
        return render_template('admin/signup.html')

    # ========== MAIN DASHBOARD ==========
    
    @app.route('/admin')
    @admin_required
    def admin_dashboard():
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
        
        return render_template('admin/dashboard.html',
            stats=stats,
            weekly=weekly,
            daily_tasks=daily_tasks,
            pinned_trackables=pinned_trackables,
            recent_entries=recent_entries,
            unlocked_achievements=unlocked_achievements
        )

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
                is_pinned=request.form.get('is_pinned') == 'on'
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
        trackables = TrackableType.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).order_by(TrackableType.display_order).all()
        
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
                url=request.form.get('url')
            )
            db.session.add(entry)
            
            # Update streak
            streak = Streak.query.filter_by(
                user_id=current_user.id,
                streak_type='daily_xp'
            ).first()
            if streak:
                streak.update_streak(entry.date)
            
            db.session.commit()
            
            trackable = TrackableType.query.get(trackable_id)
            flash(f'+{entry.get_xp()} XP for {trackable.name}!', 'success')
            return redirect(url_for('admin_dashboard'))
        
        return render_template('admin/log_entry.html', trackables=trackables, today=date.today())
    
    @app.route('/admin/quick-log/<int:trackable_id>', methods=['POST'])
    @admin_required
    def admin_quick_log(trackable_id):
        """Quick log +1 for a trackable"""
        trackable = TrackableType.query.get_or_404(trackable_id)
        if trackable.user_id != current_user.id:
            abort(403)
        
        entry = TrackableEntry(
            user_id=current_user.id,
            trackable_type_id=trackable_id,
            date=date.today(),
            count=1
        )
        db.session.add(entry)
        
        # Update streak
        streak = Streak.query.filter_by(
            user_id=current_user.id,
            streak_type='daily_xp'
        ).first()
        if streak:
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
        
        today = date.today()
        xp_earned = 0
        is_completed = False
        
        if task.task_type == 'count':
            # For count tasks, add one completion
            current_count = task.get_today_completion_count(today)
            
            if current_count < task.target_count:
                # Add a completion
                completion = TaskCompletion(
                    user_id=current_user.id,
                    task_id=task.id,
                    date=today,
                    count=1
                )
                
                # Calculate XP
                if task.xp_per_count > 0:
                    xp_earned = task.xp_per_count
                elif current_count + 1 >= task.target_count:
                    # Full completion bonus
                    xp_earned = task.xp_value
                
                completion.xp_earned = xp_earned
                db.session.add(completion)
                
                is_completed = current_count + 1 >= task.target_count
            else:
                # Already fully completed, remove last completion (toggle off)
                last_completion = TaskCompletion.query.filter_by(
                    user_id=current_user.id,
                    task_id=task.id,
                    date=today
                ).order_by(TaskCompletion.id.desc()).first()
                if last_completion:
                    xp_earned = -last_completion.xp_earned
                    db.session.delete(last_completion)
                is_completed = False
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
                    xp_earned=task.xp_value
                )
                xp_earned = task.xp_value
                db.session.add(completion)
                is_completed = True
                
                # Handle ebbinghaus tasks
                if task.repeat_type == 'ebbinghaus':
                    task.calculate_next_ebbinghaus_date()
                
                # Mark one-time tasks as completed
                if task.repeat_type == 'once':
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
            
            # Update streak
            streak = Streak.query.filter_by(
                user_id=current_user.id,
                streak_type='daily_xp'
            ).first()
            if streak:
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
                min_xp=int(request.form.get('min_xp', 0)),
                color=request.form.get('color', '#666666'),
                icon=request.form.get('icon'),
                is_max_rank=request.form.get('is_max_rank') == 'on'
            )
            db.session.add(rank)
            db.session.commit()
            flash(f'Rank "{rank.name}" created!', 'success')
            return redirect(url_for('admin_ranks'))
        return render_template('admin/rank_form.html')
    
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
            rank.min_xp = int(request.form.get('min_xp', 0))
            rank.color = request.form.get('color', '#666666')
            rank.icon = request.form.get('icon')
            rank.is_max_rank = request.form.get('is_max_rank') == 'on'
            db.session.commit()
            flash('Rank updated!', 'success')
            return redirect(url_for('admin_ranks'))
        
        return render_template('admin/rank_form.html', rank=rank)
    
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
            db.session.commit()
            flash('Settings saved!', 'success')
            return redirect(url_for('admin_settings'))
        
        return render_template('admin/settings.html', settings=settings)

    # ========== PROGRESS PAGE ==========
    
    @app.route('/admin/progress')
    @admin_required
    def admin_progress():
        stats = get_user_stats()
        weekly = get_weekly_stats()
        
        # Get last 30 days of daily logs
        thirty_days_ago = date.today() - timedelta(days=30)
        daily_logs = DailyLog.query.filter(
            DailyLog.user_id == current_user.id,
            DailyLog.date >= thirty_days_ago
        ).order_by(DailyLog.date.desc()).all()
        
        # Build calendar data
        calendar_data = {}
        for log in daily_logs:
            calendar_data[log.date.isoformat()] = {
                'xp': log.total_xp,
                'goal_met': log.goal_met
            }
        
        return render_template('admin/progress.html',
            stats=stats,
            weekly=weekly,
            daily_logs=daily_logs,
            calendar_data=calendar_data,
            now=date.today(),
            timedelta=timedelta
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
    app.run(debug=True)
