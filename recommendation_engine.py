import os
import numpy as np
from annoy import AnnoyIndex
from database import Database
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

DB_PATH = 'database/rss_feed.db'
INDEX_PATH = 'database/article_vector.index'
EMBEDDING_DIM = int(os.getenv('EMBEDDING_DIM'))

# Initialize the Annoy index and load data
annoy_index = AnnoyIndex(EMBEDDING_DIM, 'angular')
annoy_index.load(INDEX_PATH)

# Initialize the database connection
db = Database(DB_PATH)

def fetch_user_interactions():
    """
    Fetch user interactions from the database.
    """
    interactions = db.fetch_all(
        'SELECT block_id, action FROM user_interactions WHERE block_type = "article"'
    )
    return interactions

def generate_recommendations(num_recommendations=10, offset=0, exclude_ids=None):
    import numpy as np  # Ensure numpy is imported
    if exclude_ids is None:
        exclude_ids = []

    try:
        logging.debug("Starting generate_recommendations")
        logging.debug(f"exclude_ids: {exclude_ids}")

        user_interactions = fetch_user_interactions()
        logging.debug(f"user_interactions: {user_interactions}")

        # Define positive and negative actions
        positive_actions = ["thumbs_up", "back"]
        negative_actions = ["thumbs_down"]

        # Get article IDs for positive and negative interactions
        positive_article_ids = [
            int(interaction[0]) for interaction in user_interactions if interaction[1] in positive_actions
        ]
        negative_article_ids = [
            int(interaction[0]) for interaction in user_interactions if interaction[1] in negative_actions
        ]

        logging.debug(f"positive_article_ids: {positive_article_ids}")
        logging.debug(f"negative_article_ids: {negative_article_ids}")

        # Articles to exclude from recommendations
        read_article_ids = list(set(positive_article_ids + negative_article_ids))
        exclude_set = set(map(int, exclude_ids + read_article_ids))
        logging.debug(f"exclude_set: {exclude_set}")

        # Get embeddings for positive articles
        positive_vectors = []
        for article_id in positive_article_ids:
            try:
                vector = np.array(annoy_index.get_item_vector(article_id))
                positive_vectors.append(vector)
            except Exception as e:
                logging.error(f"Error fetching vector for article_id {article_id}: {e}")

        logging.debug(f"Number of positive_vectors: {len(positive_vectors)}")
        if positive_vectors:
            logging.debug(f"positive_vectors: {positive_vectors}")

        # Compute the preference vector
        if positive_vectors:
            # Use the mean of positive vectors
            preference_vector = np.mean(positive_vectors, axis=0)
            logging.debug(f"preference_vector: {preference_vector}")

            # Get similar articles using the preference vector
            recommended_ids = annoy_index.get_nns_by_vector(
                preference_vector.tolist(), num_recommendations * 10
            )
            logging.debug(f"recommended_ids after annoy_index.get_nns_by_vector: {recommended_ids}")

            # Exclude articles already read or disliked
            recommended_ids = [int(article_id) for article_id in recommended_ids if int(article_id) not in exclude_set]
            logging.debug(f"recommended_ids after exclusion: {recommended_ids}")
            recommended_ids = recommended_ids[:num_recommendations]

            if not recommended_ids:
                logging.warning("No recommended articles found after exclusion.")
                # Fallback to random articles
                return get_random_articles(num_recommendations, exclude_set)
        else:
            # No positive interactions; fetch random articles excluding disliked ones
            return get_random_articles(num_recommendations, exclude_set)

        # Fetch article details for the recommendations
        articles = []
        for article_id in recommended_ids:
            article_id = int(article_id)
            article = db.fetch_one(
                'SELECT article_id, title, description, category FROM articles WHERE article_id = ?',
                (article_id,)
            )
            if article:
                articles.append({
                    "article_id": article[0],
                    "title": article[1],
                    "description": article[2],
                    "category": article[3]
                })
            else:
                logging.error(f"Article not found in database for article_id {article_id}")

        logging.debug(f"Number of articles returned: {len(articles)}")

        return articles

    except Exception as e:
        logging.exception("Error in generate_recommendations")
        return []

def get_random_articles(num_recommendations, exclude_set):
    # Fetch all article IDs excluding those in exclude_set
    all_article_ids = db.fetch_all('SELECT article_id FROM articles')
    all_article_ids = [int(row[0]) for row in all_article_ids if int(row[0]) not in exclude_set]
    logging.debug(f"all_article_ids after exclusion: {all_article_ids}")

    if not all_article_ids:
        logging.warning("No articles available to recommend after exclusion.")
        return []

    recommended_ids = np.random.choice(
        all_article_ids, size=min(num_recommendations, len(all_article_ids)), replace=False
    )
    recommended_ids = [int(article_id) for article_id in recommended_ids]
    logging.debug(f"recommended_ids selected randomly: {recommended_ids}")

    # Fetch article details
    articles = []
    for article_id in recommended_ids:
        article = db.fetch_one(
            'SELECT article_id, title, description, category FROM articles WHERE article_id = ?',
            (article_id,)
        )
        if article:
            articles.append({
                "article_id": article[0],
                "title": article[1],
                "description": article[2],
                "category": article[3]
            })
        else:
            logging.error(f"Article not found in database for article_id {article_id}")

    logging.debug(f"Number of random articles returned: {len(articles)}")
    return articles
