"""
Main Flask application for Cryptasium
"""
from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
from datetime import datetime
import os
import markdown

from config import config
from models import db, BlogPost, YouTubeVideo, Podcast, Short, CommunityPost

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
        }
        
        return render_template('admin/dashboard.html', stats=stats)
    
    # Blog management
    @app.route('/admin/blog')
    @admin_required
    def admin_blog_list():
        """Admin blog posts list"""
        posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
        return render_template('admin/blog_list.html', posts=posts)
    
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
    
    @app.route('/admin/youtube/<int:id>/delete', methods=['POST'])
    @admin_required
    def admin_youtube_delete(id):
        """Delete YouTube video"""
        video = YouTubeVideo.query.get_or_404(id)
        db.session.delete(video)
        db.session.commit()
        flash('YouTube video deleted successfully!', 'success')
        return redirect(url_for('admin_youtube_list'))
    
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
    app.run(debug=True)

