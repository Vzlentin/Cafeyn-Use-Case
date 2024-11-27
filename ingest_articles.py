import os
from pathlib import Path
import requests
from newspaper import Article
from sentence_transformers import SentenceTransformer
from transformers import pipeline
from annoy import AnnoyIndex
from database import Database
from dotenv import load_dotenv, set_key

# Load environment variables
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)
NEWS_API_KEY = os.getenv('NEWS_API_KEY')

DB_PATH = 'database/rss_feed.db'
INDEX_PATH = 'database/article_vector.index'
CATEGORIES = ["Technology", "Business", "Sports", "Health", "Politics", "Entertainment", "Science"]

# Initialize the database connection
db = Database(DB_PATH)

# Initialize Zero-shot Classifier
classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

# Initialize Sentence Transformer for Vectorization
model = SentenceTransformer('all-MiniLM-L6-v2')
EMBEDDING_DIM = model.get_sentence_embedding_dimension()
set_key(env_path, 'EMBEDDING_DIM', str(EMBEDDING_DIM))
load_dotenv(dotenv_path=env_path)

# Ensure that articles table exists
db.execute_query('''
CREATE TABLE IF NOT EXISTS articles (
    article_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    link TEXT UNIQUE,
    category TEXT,
    published_date TEXT,
    content TEXT
)
''')

def fetch_news_articles():
    base_url = 'https://newsapi.org/v2/top-headlines'
    api_key = NEWS_API_KEY

    countries = ['us', 'gb', 'in']
    categories = ['technology', 'business', 'health']

    articles = []
    for country in countries:
        for category in categories:
            url = f'{base_url}?country={country}&category={category}&apiKey={api_key}'
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                articles.extend(data['articles'])
            else:
                print(f"Error fetching news articles: {response.status_code} - {response.text}")

    return articles

def categorize_article(title, description):
    text = f"{title}. {description}"
    result = classifier(text, CATEGORIES)
    return result['labels'][0]

def extract_full_content(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text
    except Exception as e:
        print(f"Error extracting full content for URL {url}: {e}")
        return None

def vectorize_article(title, description, content):
    text = f"{title} {description} {content}"
    if text.strip():
        embedding = model.encode(text)
        return embedding
    else:
        return None

def add_articles_to_database(articles):
    for item in articles:
        title = item.get('title', '')
        description = item.get('description', '')
        link = item.get('url', '')
        pub_date = item.get('publishedAt', '')

        # Categorize article
        category = categorize_article(title, description)

        # Extract full article content
        content = extract_full_content(link)

        if not content:
            continue  # Skip if we cannot retrieve the main content

        # Store metadata in the database
        query = '''
        INSERT OR IGNORE INTO articles (title, description, link, category, published_date, content)
        VALUES (?, ?, ?, ?, ?, ?)
        '''
        db.execute_query(query, (title, description, link, category, pub_date, content))

def rebuild_annoy_index():
    index = AnnoyIndex(EMBEDDING_DIM, 'angular')

    all_articles = db.fetch_all('SELECT article_id, title, description, content FROM articles')

    for article in all_articles:
        article_id, title, description, content = article

        # Vectorize the article
        embedding = vectorize_article(title, description, content)

        if embedding is not None:
            index.add_item(article_id, embedding)
        else:
            print(f"Skipping article {article_id} due to empty content.")

    index.build(10)
    index.save(INDEX_PATH)

def main():
    # Fetch articles from News API
    new_articles = fetch_news_articles()

    # Add new articles to the database
    add_articles_to_database(new_articles)

    # Rebuild the Annoy index from all articles
    rebuild_annoy_index()

# Run the Ingestion Pipeline
if __name__ == '__main__':
    main()
