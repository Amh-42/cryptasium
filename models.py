"""
Database models for Cryptasium application
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# ========== GAMIFICATION SYSTEM (DATABASE-DRIVEN) ==========

class SystemSettings(db.Model):
    """Global system settings stored in database"""
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get(key, default=None):
        """Get a setting value by key"""
        setting = SystemSettings.query.filter_by(key=key).first()
        return setting.value if setting else default
    
    @staticmethod
    def set(key, value, description=None):
        """Set a setting value"""
        setting = SystemSettings.query.filter_by(key=key).first()
        if setting:
            setting.value = str(value)
            if description:
                setting.description = description
        else:
            setting = SystemSettings(key=key, value=str(value), description=description)
            db.session.add(setting)
        db.session.commit()
        return setting
    
    def __repr__(self):
        return f'<SystemSettings {self.key}={self.value}>'


class Rank(db.Model):
    """Rank definitions stored in database"""
    __tablename__ = 'ranks'
    
    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.Integer, unique=True, nullable=False, index=True)  # 1-9
    code = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    points_required = db.Column(db.Integer, default=0)
    subscribers_required = db.Column(db.Integer, default=0)
    views_required = db.Column(db.Integer, default=0)
    content_required = db.Column(db.Integer, default=0)
    color = db.Column(db.String(20), default='#666666')
    icon = db.Column(db.String(10), default='⭐')
    is_max_rank = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get_all_ordered():
        """Get all ranks ordered by level"""
        return Rank.query.order_by(Rank.level.asc()).all()
    
    @staticmethod
    def get_max_rank():
        """Get the maximum rank"""
        return Rank.query.filter_by(is_max_rank=True).first()
    
    def to_dict(self):
        return {
            'code': self.code,
            'name': self.name,
            'points': self.points_required,
            'subscribers': self.subscribers_required,
            'views': self.views_required,
            'content': self.content_required,
            'color': self.color,
            'icon': self.icon,
            'level': self.level,
            'is_max_rank': self.is_max_rank
        }
    
    def __repr__(self):
        return f'<Rank L{self.level}: {self.code} - {self.name}>'


class ContentPointValue(db.Model):
    """Point values for different content types"""
    __tablename__ = 'content_point_values'
    
    id = db.Column(db.Integer, primary_key=True)
    content_type = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    points = db.Column(db.Float, default=0)
    description = db.Column(db.String(500))
    icon = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get_points(content_type, default=0):
        """Get points for a content type"""
        cpv = ContentPointValue.query.filter_by(content_type=content_type).first()
        return cpv.points if cpv else default
    
    @staticmethod
    def get_all_as_dict():
        """Get all content point values as a dictionary"""
        values = ContentPointValue.query.all()
        return {v.content_type: v.points for v in values}
    
    def __repr__(self):
        return f'<ContentPointValue {self.content_type}={self.points}>'


class DailyTask(db.Model):
    """Daily XP task definitions stored in database"""
    __tablename__ = 'daily_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    task_key = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    xp_value = db.Column(db.Integer, default=0)
    icon = db.Column(db.String(10))
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get_active_tasks():
        """Get all active daily tasks ordered by display order"""
        return DailyTask.query.filter_by(is_active=True).order_by(DailyTask.display_order.asc()).all()
    
    @staticmethod
    def get_task(task_key):
        """Get a task by key"""
        return DailyTask.query.filter_by(task_key=task_key).first()
    
    def __repr__(self):
        return f'<DailyTask {self.task_key}: {self.xp_value} XP>'


class WeeklyRequirement(db.Model):
    """Weekly content requirements stored in database"""
    __tablename__ = 'weekly_requirements'
    
    id = db.Column(db.Integer, primary_key=True)
    content_type = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    required_count = db.Column(db.Integer, default=1)
    icon = db.Column(db.String(10))
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get_active_requirements():
        """Get all active weekly requirements ordered by display order"""
        return WeeklyRequirement.query.filter_by(is_active=True).order_by(WeeklyRequirement.display_order.asc()).all()
    
    def __repr__(self):
        return f'<WeeklyRequirement {self.content_type}: {self.required_count}>'


# Helper functions that now read from database
def get_video_content_type(duration_seconds):
    """Determine video content type based on duration in seconds"""
    # Get thresholds from settings or use defaults
    shorts_max = int(SystemSettings.get('shorts_duration_max', '60'))
    short_longs_max = int(SystemSettings.get('short_longs_duration_max', '300'))
    mid_longs_max = int(SystemSettings.get('mid_longs_duration_max', '480'))
    
    if duration_seconds <= shorts_max:
        return 'shorts'
    elif duration_seconds <= short_longs_max:
        return 'short_longs'
    elif duration_seconds <= mid_longs_max:
        return 'mid_longs'
    else:
        return 'longs'


def get_rank_for_stats(points, subscribers, views, content_count):
    """Determine current rank based on stats. Returns rank dict and next rank dict."""
    ranks = Rank.get_all_ordered()
    
    if not ranks:
        # Fallback if no ranks in database
        unranked = {'code': 'UN', 'name': 'Unranked', 'points': 0, 'subscribers': 0, 'views': 0, 'content': 0, 'color': '#666666', 'icon': 'PNG/UN.png'}
        return unranked, None
    
    current_rank = None
    next_rank = None
    
    for i, rank in enumerate(ranks):
        rank_dict = rank.to_dict()
        # Check if ALL requirements for this rank are met
        if (points >= rank.points_required and 
            subscribers >= rank.subscribers_required and 
            views >= rank.views_required and 
            content_count >= rank.content_required):
            current_rank = rank_dict
            # Get next rank if exists
            if i + 1 < len(ranks):
                next_rank = ranks[i + 1].to_dict()
        else:
            # This rank not achieved, it's the next target
            if current_rank is None:
                # Get Unranked from database or use fallback
                unranked_db = Rank.query.filter_by(code='UN').first()
                if unranked_db:
                    current_rank = unranked_db.to_dict()
                else:
                    current_rank = {'code': 'UN', 'name': 'Unranked', 'points': 0, 'subscribers': 0, 'views': 0, 'content': 0, 'color': '#666666', 'icon': 'PNG/UN.png'}
            next_rank = rank_dict
            break
    
    # If all ranks achieved
    if current_rank and not next_rank and current_rank.get('is_max_rank'):
        next_rank = None  # Max rank achieved
    
    return current_rank, next_rank


def get_content_points():
    """Get content point values from database"""
    return ContentPointValue.get_all_as_dict()


def get_daily_xp_goal():
    """Get daily XP goal from settings"""
    return int(SystemSettings.get('daily_xp_goal', '50'))


def get_perfect_week_bonus():
    """Get perfect week bonus XP from settings"""
    return int(SystemSettings.get('perfect_week_bonus', '500'))


def get_points_name():
    """Get the name for points (XP, PT, etc.)"""
    return SystemSettings.get('points_name', 'XP')




class GamificationStats(db.Model):
    """Gamification statistics and channel metrics"""
    __tablename__ = 'gamification_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Channel stats (fetched from YouTube API)
    subscriber_count = db.Column(db.Integer, default=0)
    total_channel_views = db.Column(db.Integer, default=0)
    
    # Calculated stats
    total_points = db.Column(db.Integer, default=0)
    total_content_count = db.Column(db.Integer, default=0)
    total_views = db.Column(db.Integer, default=0)
    
    # Current rank info
    current_rank_code = db.Column(db.String(10), default='UNRANKED')
    current_rank_name = db.Column(db.String(50), default='Unranked')
    
    # Content breakdown
    blog_count = db.Column(db.Integer, default=0)
    shorts_count = db.Column(db.Integer, default=0)
    short_longs_count = db.Column(db.Integer, default=0)  # Videos < 5 min
    podcast_count = db.Column(db.Integer, default=0)
    mid_longs_count = db.Column(db.Integer, default=0)    # Videos 5-15 min
    longs_count = db.Column(db.Integer, default=0)        # Videos > 15 min
    
    # Points breakdown
    blog_points = db.Column(db.Integer, default=0)
    shorts_points = db.Column(db.Integer, default=0)
    short_longs_points = db.Column(db.Integer, default=0)
    podcast_points = db.Column(db.Integer, default=0)
    mid_longs_points = db.Column(db.Integer, default=0)
    longs_points = db.Column(db.Integer, default=0)
    subscriber_points = db.Column(db.Integer, default=0)  # 1 subscriber = 20 pts
    views_points = db.Column(db.Integer, default=0)       # 1 view = 0.5 pts
    daily_xp_points = db.Column(db.Integer, default=0)    # Accumulated daily XP from tasks
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_sync_at = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<GamificationStats {self.current_rank_code} - {self.total_points} XP>'
    
    def calculate_rank(self):
        """Calculate and update current rank based on stats"""
        current_rank, next_rank = get_rank_for_stats(
            self.total_points, 
            self.subscriber_count, 
            self.total_views, 
            self.total_content_count
        )
        self.current_rank_code = current_rank['code']
        self.current_rank_name = current_rank['name']
        return current_rank, next_rank
    
    def get_progress_to_next_rank(self):
        """Get progress percentages for each requirement to next rank"""
        current_rank, next_rank = get_rank_for_stats(
            self.total_points,
            self.subscriber_count,
            self.total_views,
            self.total_content_count
        )
        
        if not next_rank:
            return None  # Max rank achieved
        
        def safe_progress(current, target):
            if target == 0:
                return 100
            return min(100, int((current / target) * 100))
        
        return {
            'points': safe_progress(self.total_points, next_rank['points']),
            'subscribers': safe_progress(self.subscriber_count, next_rank['subscribers']),
            'views': safe_progress(self.total_views, next_rank['views']),
            'content': safe_progress(self.total_content_count, next_rank['content']),
            'next_rank': next_rank
        }
    
    def to_dict(self):
        current_rank, next_rank = self.calculate_rank()
        progress = self.get_progress_to_next_rank()
        
        return {
            'total_points': self.total_points,
            'subscriber_count': self.subscriber_count,
            'total_views': self.total_views,
            'total_content_count': self.total_content_count,
            'current_rank': current_rank,
            'next_rank': next_rank,
            'progress': progress,
            'content_breakdown': {
                'blog': {'count': self.blog_count, 'points': self.blog_points},
                'shorts': {'count': self.shorts_count, 'points': self.shorts_points},
                'short_longs': {'count': self.short_longs_count, 'points': self.short_longs_points},
                'podcast': {'count': self.podcast_count, 'points': self.podcast_points},
                'mid_longs': {'count': self.mid_longs_count, 'points': self.mid_longs_points},
                'longs': {'count': self.longs_count, 'points': self.longs_points},
                'subscribers': {'count': self.subscriber_count, 'points': self.subscriber_points},
                'views': {'count': self.total_views, 'points': self.views_points},
            },
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class BlogPost(db.Model):
    """Blog post model"""
    __tablename__ = 'blog_posts'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    excerpt = db.Column(db.Text)
    content = db.Column(db.Text, nullable=False)
    featured_image = db.Column(db.String(500))
    author = db.Column(db.String(100), default='Cryptasium Team')
    published = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    views = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<BlogPost {self.title}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'slug': self.slug,
            'excerpt': self.excerpt,
            'content': self.content,
            'featured_image': self.featured_image,
            'author': self.author,
            'published': self.published,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'views': self.views
        }


class YouTubeVideo(db.Model):
    """YouTube video model"""
    __tablename__ = 'youtube_videos'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    video_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    thumbnail_url = db.Column(db.String(500))
    duration = db.Column(db.String(20))  # e.g., "10:30"
    duration_seconds = db.Column(db.Integer, default=0)  # Duration in seconds for categorization
    content_type = db.Column(db.String(20), default='longs')  # shorts, short_longs, mid_longs, longs
    published = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    views = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<YouTubeVideo {self.title}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'video_id': self.video_id,
            'thumbnail_url': self.thumbnail_url,
            'duration': self.duration,
            'published': self.published,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'views': self.views,
            'likes': self.likes
        }


class Podcast(db.Model):
    """Podcast episode model"""
    __tablename__ = 'podcasts'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    episode_number = db.Column(db.Integer)
    audio_url = db.Column(db.String(500))
    thumbnail_url = db.Column(db.String(500))
    duration = db.Column(db.String(20))
    published = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    views = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<Podcast {self.title}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'episode_number': self.episode_number,
            'audio_url': self.audio_url,
            'thumbnail_url': self.thumbnail_url,
            'duration': self.duration,
            'published': self.published,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'views': self.views
        }


class Short(db.Model):
    """Short video model"""
    __tablename__ = 'shorts'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    video_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    thumbnail_url = db.Column(db.String(500))
    duration = db.Column(db.String(20))
    published = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    views = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<Short {self.title}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'video_id': self.video_id,
            'thumbnail_url': self.thumbnail_url,
            'duration': self.duration,
            'published': self.published,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'views': self.views,
            'likes': self.likes
        }


class CommunityPost(db.Model):
    """Community post model"""
    __tablename__ = 'community_posts'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(100), default='Community Member')
    category = db.Column(db.String(50))  # e.g., "Discussion", "Question", "Announcement"
    published = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    views = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<CommunityPost {self.title}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'author': self.author,
            'category': self.category,
            'published': self.published,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'views': self.views,
            'likes': self.likes
        }


class TopicIdea(db.Model):
    """Topic idea submission model"""
    __tablename__ = 'topic_ideas'
    
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    email = db.Column(db.String(200))
    name = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')  # pending, reviewed, approved, rejected
    reviewed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    reviewed_at = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<TopicIdea {self.topic}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'topic': self.topic,
            'description': self.description,
            'email': self.email,
            'name': self.name,
            'status': self.status,
            'reviewed': self.reviewed,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None
        }


# ========== DAILY PROGRESS TRACKING SYSTEM ==========

# Daily XP task definitions
DAILY_XP_TASKS = {
    'research': {'name': 'Research/Scripting', 'xp': 15, 'icon': '📚', 'description': 'Deep work for Long Form/Blog'},
    'recording': {'name': 'Recording/Editing', 'xp': 20, 'icon': '🎬', 'description': 'Technical execution'},
    'engagement': {'name': 'Community Engagement', 'xp': 10, 'icon': '💬', 'description': 'Replying to comments/Discord'},
    'learning': {'name': 'Learning/Skill-Up', 'xp': 5, 'icon': '🎓', 'description': 'Watching masterclass or technical whitepaper'}
}

DAILY_XP_GOAL = 50

# Weekly content requirements
WEEKLY_CONTENT_REQUIREMENTS = {
    'long_form': {'name': 'Long Form (YouTube)', 'count': 1, 'icon': '🎯', 'description': 'The "Boss Battle"'},
    'shorts': {'name': 'Shorts (YouTube)', 'count': 2, 'icon': '⚔️', 'description': 'The "Skirmishes"'},
    'blog': {'name': 'Blog (Technical Writing)', 'count': 1, 'icon': '📝', 'description': 'The "Knowledge Base"'},
    'podcast': {'name': 'Podcast (Audio/Interview)', 'count': 1, 'icon': '🎙️', 'description': 'The "Networking/Philosophy"'}
}

# 9-Level Architect Rank System
ARCHITECT_RANKS = [
    {
        'level': 1,
        'code': 'BT',
        'name': 'Beginner Token',
        'milestone': 'Post for 4 weeks straight',
        'focus': 'Consistency. Just finish the 5 items.',
        'weeks_required': 4,
        'color': '#8B4513',  # Saddle brown
        'icon': '🌱'
    },
    {
        'level': 2,
        'code': 'HB',
        'name': 'Habit Builder',
        'milestone': '90-day streak of Daily XP',
        'focus': 'Discipline. No missed days.',
        'days_required': 90,
        'color': '#CD853F',  # Peru
        'icon': '🔥'
    },
    {
        'level': 3,
        'code': 'SO',
        'name': 'Standing Out',
        'milestone': 'Reach 1,000 Subs / 50 total videos',
        'focus': 'Mastery. Refining the edit and audio.',
        'subscribers_required': 1000,
        'content_required': 50,
        'color': '#B8860B',  # Dark goldenrod
        'icon': '⭐'
    },
    {
        'level': 4,
        'code': 'TP',
        'name': 'Team Player',
        'milestone': 'First Collab or Guest on Podcast',
        'focus': 'Leading. Working with others.',
        'collabs_required': 1,
        'color': '#4682B4',  # Steel blue
        'icon': '🤝'
    },
    {
        'level': 5,
        'code': 'FL',
        'name': 'Flight Lead',
        'milestone': 'Launch a "Series" or Playlists',
        'focus': 'Execution. Organizing content into themes.',
        'series_required': 1,
        'color': '#6A5ACD',  # Slate blue
        'icon': '🚀'
    },
    {
        'level': 6,
        'code': 'MS',
        'name': 'Master Strategist',
        'milestone': 'Revenue Goal / Sponsorships',
        'focus': 'Wealth. Making the channel profitable.',
        'revenue_milestone': True,
        'color': '#FFD700',  # Gold
        'icon': '💰'
    },
    {
        'level': 7,
        'code': 'EA',
        'name': 'Empire Architect',
        'milestone': 'Hire an editor or researcher',
        'focus': 'Building. Scaling the brand beyond yourself.',
        'team_size': 1,
        'color': '#9932CC',  # Dark orchid
        'icon': '🏛️'
    },
    {
        'level': 8,
        'code': 'LF',
        'name': 'Legacy Forger',
        'milestone': '100k Subs / A "Masterwork" Video',
        'focus': 'Legacy. One video that goes truly viral.',
        'subscribers_required': 100000,
        'viral_video': True,
        'color': '#00CED1',  # Dark turquoise
        'icon': '🔮'
    },
    {
        'level': 9,
        'code': 'AL',
        'name': 'Alpha Legend',
        'milestone': '1M Subs / Complete Freedom',
        'focus': 'Alpha. You are the authority in tech.',
        'subscribers_required': 1000000,
        'color': '#FF2222',  # Cryptasium red
        'icon': '👑'
    }
]


class DailyXPLog(db.Model):
    """Track daily XP tasks and streaks"""
    __tablename__ = 'daily_xp_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True, unique=True)
    
    # Task completions
    research_completed = db.Column(db.Boolean, default=False)
    recording_completed = db.Column(db.Boolean, default=False)
    engagement_completed = db.Column(db.Boolean, default=False)
    learning_completed = db.Column(db.Boolean, default=False)
    
    # Calculated XP for the day
    total_xp = db.Column(db.Integer, default=0)
    goal_met = db.Column(db.Boolean, default=False)
    
    # Notes for the day
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def calculate_xp(self):
        """Calculate total XP based on completed tasks"""
        xp = 0
        
        # Get XP values from database
        research_task = DailyTask.get_task('research')
        recording_task = DailyTask.get_task('recording')
        engagement_task = DailyTask.get_task('engagement')
        learning_task = DailyTask.get_task('learning')
        
        if self.research_completed and research_task:
            xp += research_task.xp_value
        if self.recording_completed and recording_task:
            xp += recording_task.xp_value
        if self.engagement_completed and engagement_task:
            xp += engagement_task.xp_value
        if self.learning_completed and learning_task:
            xp += learning_task.xp_value
        
        self.total_xp = xp
        self.goal_met = xp >= get_daily_xp_goal()
        return xp
    
    def __repr__(self):
        return f'<DailyXPLog {self.date} - {self.total_xp} XP>'


class WeeklyProgress(db.Model):
    """Track weekly content production (Full House)"""
    __tablename__ = 'weekly_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Week identifier (ISO week format: YYYY-WW)
    year = db.Column(db.Integer, nullable=False)
    week_number = db.Column(db.Integer, nullable=False)
    week_start = db.Column(db.Date, nullable=False, index=True)
    week_end = db.Column(db.Date, nullable=False)
    
    # Content completion tracking
    long_form_completed = db.Column(db.Integer, default=0)  # Target: 1
    shorts_completed = db.Column(db.Integer, default=0)      # Target: 2
    blog_completed = db.Column(db.Integer, default=0)        # Target: 1
    podcast_completed = db.Column(db.Integer, default=0)     # Target: 1
    
    # Perfect week status
    perfect_week = db.Column(db.Boolean, default=False)
    multiplier_active = db.Column(db.Boolean, default=False)
    
    # Bonus XP from multiplier
    bonus_xp = db.Column(db.Integer, default=0)
    
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('year', 'week_number', name='unique_year_week'),
    )
    
    def check_perfect_week(self):
        """Check if all weekly requirements are met"""
        # Get requirements from database
        requirements = {r.content_type: r.required_count for r in WeeklyRequirement.get_active_requirements()}
        
        self.perfect_week = (
            self.long_form_completed >= requirements.get('long_form', 1) and
            self.shorts_completed >= requirements.get('shorts', 2) and
            self.blog_completed >= requirements.get('blog', 1) and
            self.podcast_completed >= requirements.get('podcast', 1)
        )
        return self.perfect_week
    
    def get_completion_status(self):
        """Get completion status for each content type"""
        # Get requirements from database
        requirements = {r.content_type: r.required_count for r in WeeklyRequirement.get_active_requirements()}
        
        return {
            'long_form': {
                'completed': self.long_form_completed,
                'required': requirements.get('long_form', 1),
                'done': self.long_form_completed >= requirements.get('long_form', 1)
            },
            'shorts': {
                'completed': self.shorts_completed,
                'required': requirements.get('shorts', 2),
                'done': self.shorts_completed >= requirements.get('shorts', 2)
            },
            'blog': {
                'completed': self.blog_completed,
                'required': requirements.get('blog', 1),
                'done': self.blog_completed >= requirements.get('blog', 1)
            },
            'podcast': {
                'completed': self.podcast_completed,
                'required': requirements.get('podcast', 1),
                'done': self.podcast_completed >= requirements.get('podcast', 1)
            }
        }
    
    def __repr__(self):
        return f'<WeeklyProgress {self.year}-W{self.week_number} - Perfect: {self.perfect_week}>'


class MonthlyProgress(db.Model):
    """Track monthly rank evaluation"""
    __tablename__ = 'monthly_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Month identifier
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    
    # Output Volume (e.g., 20/20 pieces of content)
    content_target = db.Column(db.Integer, default=20)
    content_produced = db.Column(db.Integer, default=0)
    
    # Retention Score (average view duration improvement)
    avg_view_duration_start = db.Column(db.Float, default=0)  # At start of month
    avg_view_duration_end = db.Column(db.Float, default=0)    # At end of month
    retention_improved = db.Column(db.Boolean, default=False)
    skill_point_earned = db.Column(db.Boolean, default=False)
    
    # Monthly Sprint - experimental content
    experimental_content = db.Column(db.String(500))  # Description of experimental piece
    experimental_completed = db.Column(db.Boolean, default=False)
    experimental_type = db.Column(db.String(100))  # e.g., "collab", "new style", "series"
    
    # Perfect weeks count this month
    perfect_weeks = db.Column(db.Integer, default=0)
    
    # Total XP earned this month
    total_xp = db.Column(db.Integer, default=0)
    
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('year', 'month', name='unique_year_month'),
    )
    
    def __repr__(self):
        return f'<MonthlyProgress {self.year}-{self.month:02d}>'


class YearlyMilestones(db.Model):
    """Track yearly legacy milestones"""
    __tablename__ = 'yearly_milestones'
    
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, unique=True)
    
    # Quarterly Boss Reviews - Brand Assets
    q1_review_completed = db.Column(db.Boolean, default=False)
    q1_review_notes = db.Column(db.Text)
    q2_review_completed = db.Column(db.Boolean, default=False)
    q2_review_notes = db.Column(db.Text)
    q3_review_completed = db.Column(db.Boolean, default=False)
    q3_review_notes = db.Column(db.Text)
    q4_review_completed = db.Column(db.Boolean, default=False)
    q4_review_notes = db.Column(db.Text)
    
    # Brand asset upgrades tracking
    website_updated = db.Column(db.Boolean, default=False)
    intro_outro_updated = db.Column(db.Boolean, default=False)
    equipment_upgraded = db.Column(db.Boolean, default=False)
    thumbnail_style_updated = db.Column(db.Boolean, default=False)
    
    # Veritasium Metric - Evergreen Value
    evergreen_video_count = db.Column(db.Integer, default=0)  # Videos from 6+ months ago still getting views
    evergreen_view_threshold = db.Column(db.Integer, default=100)  # Min views/month to count as evergreen
    
    # Fireship Metric - Production Speed
    avg_production_time_start = db.Column(db.Float)  # Hours per video at year start
    avg_production_time_current = db.Column(db.Float)  # Current hours per video
    efficiency_improved = db.Column(db.Boolean, default=False)
    
    # Total stats for the year
    total_xp = db.Column(db.Integer, default=0)
    total_content = db.Column(db.Integer, default=0)
    perfect_weeks = db.Column(db.Integer, default=0)
    streak_longest = db.Column(db.Integer, default=0)
    
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<YearlyMilestones {self.year}>'


class ArchitectRankProgress(db.Model):
    """Track progress toward 9-level Architect rank system"""
    __tablename__ = 'architect_rank_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Current rank (1-9)
    current_level = db.Column(db.Integer, default=0)
    current_rank_code = db.Column(db.String(10), default='UNRANKED')
    current_rank_name = db.Column(db.String(100), default='Unranked')
    
    # Streak tracking
    daily_streak = db.Column(db.Integer, default=0)
    weekly_streak = db.Column(db.Integer, default=0)  # Consecutive perfect weeks
    longest_daily_streak = db.Column(db.Integer, default=0)
    longest_weekly_streak = db.Column(db.Integer, default=0)
    
    # Milestone progress
    weeks_consistent = db.Column(db.Integer, default=0)  # For L1: BT
    days_xp_streak = db.Column(db.Integer, default=0)    # For L2: HB
    collabs_completed = db.Column(db.Integer, default=0) # For L4: TP
    series_launched = db.Column(db.Integer, default=0)   # For L5: FL
    revenue_achieved = db.Column(db.Boolean, default=False)  # For L6: MS
    team_hired = db.Column(db.Boolean, default=False)    # For L7: EA
    viral_video_achieved = db.Column(db.Boolean, default=False)  # For L8: LF
    
    # Total XP accumulated (lifetime)
    lifetime_xp = db.Column(db.Integer, default=0)
    
    # Last activity tracking
    last_daily_log = db.Column(db.Date)
    last_perfect_week = db.Column(db.Date)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def calculate_current_rank(self, subscriber_count, total_content):
        """Calculate current Architect rank based on progress"""
        for rank in reversed(ARCHITECT_RANKS):
            level = rank['level']
            
            # Check requirements for each level
            if level == 1:  # BT - 4 weeks consistent
                if self.weeks_consistent >= rank.get('weeks_required', 4):
                    self.current_level = level
                    self.current_rank_code = rank['code']
                    self.current_rank_name = rank['name']
                    continue
                    
            elif level == 2:  # HB - 90-day streak
                if self.days_xp_streak >= rank.get('days_required', 90):
                    self.current_level = level
                    self.current_rank_code = rank['code']
                    self.current_rank_name = rank['name']
                    continue
                    
            elif level == 3:  # SO - 1k subs, 50 videos
                if (subscriber_count >= rank.get('subscribers_required', 1000) and 
                    total_content >= rank.get('content_required', 50)):
                    self.current_level = level
                    self.current_rank_code = rank['code']
                    self.current_rank_name = rank['name']
                    continue
                    
            elif level == 4:  # TP - First collab
                if self.collabs_completed >= rank.get('collabs_required', 1):
                    self.current_level = level
                    self.current_rank_code = rank['code']
                    self.current_rank_name = rank['name']
                    continue
                    
            elif level == 5:  # FL - Launch series
                if self.series_launched >= rank.get('series_required', 1):
                    self.current_level = level
                    self.current_rank_code = rank['code']
                    self.current_rank_name = rank['name']
                    continue
                    
            elif level == 6:  # MS - Revenue
                if self.revenue_achieved:
                    self.current_level = level
                    self.current_rank_code = rank['code']
                    self.current_rank_name = rank['name']
                    continue
                    
            elif level == 7:  # EA - Hire team
                if self.team_hired:
                    self.current_level = level
                    self.current_rank_code = rank['code']
                    self.current_rank_name = rank['name']
                    continue
                    
            elif level == 8:  # LF - 100k subs + viral
                if (subscriber_count >= rank.get('subscribers_required', 100000) and 
                    self.viral_video_achieved):
                    self.current_level = level
                    self.current_rank_code = rank['code']
                    self.current_rank_name = rank['name']
                    continue
                    
            elif level == 9:  # AL - 1M subs
                if subscriber_count >= rank.get('subscribers_required', 1000000):
                    self.current_level = level
                    self.current_rank_code = rank['code']
                    self.current_rank_name = rank['name']
                    break
        
        return self.current_level, self.current_rank_code, self.current_rank_name
    
    def get_next_rank(self):
        """Get the next rank to achieve"""
        if self.current_level >= 9:
            return None
        
        next_level = self.current_level + 1
        for rank in ARCHITECT_RANKS:
            if rank['level'] == next_level:
                return rank
        return ARCHITECT_RANKS[0] if self.current_level == 0 else None
    
    def __repr__(self):
        return f'<ArchitectRankProgress L{self.current_level}: {self.current_rank_code}>'
