"""
Database models for Cryptasium application
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

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

