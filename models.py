"""
Database models for Cryptasium application
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# ========== GAMIFICATION SYSTEM ==========

# Rank definitions with requirements
RANKS = [
    {
        'code': 'CT',
        'name': 'Copper Token',
        'points': 100,
        'subscribers': 5,
        'views': 200,
        'content': 1,
        'color': '#B87333',  # Copper
        'icon': '🥉'
    },
    {
        'code': 'MT',
        'name': 'Metal Token',
        'points': 5000,
        'subscribers': 100,
        'views': 10000,
        'content': 20,
        'color': '#71797E',  # Steel gray
        'icon': '⚙️'
    },
    {
        'code': 'TT',
        'name': 'Titanium Token',
        'points': 10000,
        'subscribers': 1000,
        'views': 20000,
        'content': 40,
        'color': '#878681',  # Titanium
        'icon': '🔩'
    },
    {
        'code': 'NTB',
        'name': 'Noble Token Bronze',
        'points': 50000,
        'subscribers': 5000,
        'views': 100000,
        'content': 80,
        'color': '#CD7F32',  # Bronze
        'icon': '🥈'
    },
    {
        'code': 'IBB',
        'name': 'Iron Bronze Bar',
        'points': 200000,
        'subscribers': 10000,
        'views': 400000,
        'content': 160,
        'color': '#A97142',  # Iron bronze
        'icon': '🏅'
    },
    {
        'code': 'GEB',
        'name': 'Gold Elite Bar',
        'points': 1000000,
        'subscribers': 50000,
        'views': 2000000,
        'content': 320,
        'color': '#FFD700',  # Gold
        'icon': '🥇'
    },
    {
        'code': 'CA',
        'name': 'Crystal Ascension',
        'points': 5000000,
        'subscribers': 100000,
        'views': 10000000,
        'content': 640,
        'color': '#E0FFFF',  # Crystal
        'icon': '💎'
    },
    {
        'code': 'AL',
        'name': 'Apex Legend',
        'points': 20000000,
        'subscribers': 1000000000,
        'views': 40000000,
        'content': 1280,
        'color': '#0ea5e9',  # Cryptasium sky blue
        'icon': '👑'
    }
]

# Content type point values
CONTENT_POINTS = {
    'blog': 50,
    'shorts': 100,
    'short_longs': 200,  # Videos under 5 min
    'podcast': 400,
    'mid_longs': 800,    # Videos 5-15 min
    'longs': 1000        # Videos over 15 min
}

def get_video_content_type(duration_seconds):
    """Determine video content type based on duration in seconds"""
    if duration_seconds <= 60:  # 1 minute or less
        return 'shorts'
    elif duration_seconds <= 300:  # 5 minutes or less
        return 'short_longs'
    elif duration_seconds <= 480:  # 8 minutes or less
        return 'mid_longs'
    else:
        return 'longs'

def get_rank_for_stats(points, subscribers, views, content_count):
    """Determine current rank based on stats. Returns rank dict and next rank dict."""
    current_rank = None
    next_rank = None
    
    for i, rank in enumerate(RANKS):
        # Check if ALL requirements for this rank are met
        if (points >= rank['points'] and 
            subscribers >= rank['subscribers'] and 
            views >= rank['views'] and 
            content_count >= rank['content']):
            current_rank = rank
            # Get next rank if exists
            if i + 1 < len(RANKS):
                next_rank = RANKS[i + 1]
        else:
            # This rank not achieved, it's the next target
            if current_rank is None:
                current_rank = {'code': 'UNRANKED', 'name': 'Unranked', 'points': 0, 'subscribers': 0, 'views': 0, 'content': 0, 'color': '#666', 'icon': '⭐'}
            next_rank = rank
            break
    
    # If all ranks achieved
    if current_rank and not next_rank and current_rank['code'] == 'AL':
        next_rank = None  # Max rank achieved
    
    return current_rank, next_rank


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
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_sync_at = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<GamificationStats {self.current_rank_code} - {self.total_points} PT>'
    
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
