from flask import Flask, render_template, redirect, url_for, session
from datetime import datetime
from database import Database
from recommendation_engine import generate_recommendations

app = Flask(__name__)
app.secret_key = 'baba'  # Replace with a secure key
db = Database('database/rss_feed.db')

def log_user_interaction(block_id, block_type, action):
    timestamp = datetime.now().isoformat()
    query = '''
    INSERT INTO user_interactions (block_id, block_type, action, timestamp)
    VALUES (?, ?, ?, ?)
    '''
    db.execute_query(query, (block_id, block_type, action, timestamp))

@app.route('/')
def home():
    session.clear()
    recommendations = generate_recommendations(num_recommendations=1)
    if recommendations:
        article = recommendations[0]
        session['history'] = [article['article_id']]
        return render_template('article.html', article=article, can_go_back=False)
    return "No articles available"

@app.route('/next')
def next_article():
    history = session.get('history', [])
    recommendations = generate_recommendations(num_recommendations=1, exclude_ids=history)
    if recommendations:
        article = recommendations[0]
        history.append(article['article_id'])
        session['history'] = history
        can_go_back = len(history) > 1
        # Log the 'next' action with the new article ID
        log_user_interaction(article['article_id'], 'article', 'next')
        return render_template('article.html', article=article, can_go_back=can_go_back)
    return "No more articles"

@app.route('/back')
def previous_article():
    history = session.get('history', [])
    if len(history) > 1:
        # Remove the current article
        history.pop()
        # Get the previous article ID
        previous_article_id = history[-1]
        session['history'] = history
        # Fetch the article from the database
        article = db.fetch_one(
            'SELECT article_id, title, description, category FROM articles WHERE article_id = ?',
            (previous_article_id,)
        )
        if article:
            article_data = dict(zip(['article_id', 'title', 'description', 'category'], article))
            can_go_back = len(history) > 1
            # Log the 'back' action with the previous article ID
            log_user_interaction(article_data['article_id'], 'article', 'back')
            return render_template('article.html', article=article_data, can_go_back=can_go_back)
        return "Article not found"
    return "No previous articles"

@app.route('/article/<int:article_id>')
def article(article_id):
    article = db.fetch_one(
        '''SELECT article_id, title, description, content, category, published_date 
           FROM articles WHERE article_id = ?''',
        (article_id,)
    )
    if article:
        log_user_interaction(article_id, 'article', 'view')
        article_data = dict(zip(
            ['article_id', 'title', 'description', 'content', 'category', 'published_date'], article
        ))
        history = session.get('history', [])
        can_go_back = len(history) > 1
        return render_template('article.html', article=article_data, can_go_back=can_go_back)
    return "Article not found", 404

@app.route('/thumbs_up/<int:article_id>')
def thumbs_up(article_id):
    log_user_interaction(article_id, 'article', 'thumbs_up')
    return redirect(url_for('next_article'))

@app.route('/thumbs_down/<int:article_id>')
def thumbs_down(article_id):
    log_user_interaction(article_id, 'article', 'thumbs_down')
    return redirect(url_for('next_article'))

if __name__ == '__main__':
    app.run(debug=True)
