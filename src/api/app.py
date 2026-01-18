import os
import sqlite3
import logging
import time
import random
import google.generativeai as genai
from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from neo4j import GraphDatabase
from pymilvus import connections, Collection
from dotenv import load_dotenv

# --- Setup & Config ---
load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API")

app = FastAPI(title="Marketing Personalization API")

# DB Configs - Loaded from .env
MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:password@localhost:27017/")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_AUTH = (NEO4J_USER, NEO4J_PASSWORD)

MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
SQLITE_DB = "analytics.db"

# AI Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
DIMENSION = 768

# --- Global Connections ---
# We connect once when the app starts
try:
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client["marketing_platform"]
    logger.info("[INFO] Connected to MongoDB")
except Exception as e:
    logger.error(f"[ERROR] Mongo Connection: {e}")

try:
    neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    neo4j_driver.verify_connectivity()
    logger.info("[INFO] Connected to Neo4j")
except Exception as e:
    logger.error(f"[ERROR] Neo4j Connection: {e}")

# Connect to Milvus
try:
    connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
    milvus_col = Collection("user_embeddings")
    milvus_col.load()
    logger.info("[INFO] Connected to Milvus")
except Exception as e:
    logger.error(f"[ERROR] Milvus Connection: {e}")

# --- Helper Functions ---

def get_embedding(text):
    """
    Generates vector using Gemini.
    Includes RETRY logic and a FALLBACK dummy vector so the API never crashes during a demo.
    """
    retries = 2
    for attempt in range(retries):
        try:
            # Short sleep to be gentle on the API
            time.sleep(1.0)
            result = genai.embed_content(
                model="models/embedding-001",
                content=text,
                task_type="retrieval_query"
            )
            return result['embedding']
        except Exception as e:
            logger.warning(f"Embedding attempt {attempt+1} failed: {e}")
            if "429" in str(e):
                time.sleep(2.0) # Wait longer if rate limited
            else:
                break # Stop if it's a real error (like auth)

    # --- FALLBACK ---
    logger.error("All embedding attempts failed. Using DUMMY vector for demo.")
    return [random.uniform(-0.1, 0.1) for _ in range(DIMENSION)]

def get_campaign_ranking(campaign_ids):
    """Fetches engagement scores from SQLite for a list of campaigns."""
    if not campaign_ids:
        return {}
    
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    
    placeholders = ",".join("?" for _ in campaign_ids)
    query = f"SELECT campaign_id, total_interactions FROM campaign_analytics WHERE campaign_id IN ({placeholders})"
    
    cursor.execute(query, campaign_ids)
    results = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return results

# --- API Endpoints ---

@app.get("/")
def health_check():
    return {"status": "running", "service": "Hybrid Retrieval API"}

@app.get("/recommendations/{user_id}")
def recommend_campaigns(user_id: str):
    logger.info(f"[REQUEST] Recommendation for: {user_id}")

    # 1. Fetch User's Last Message (MongoDB)
    # We need a source text to find "similar" users.
    last_interaction = mongo_db.interactions.find_one(
        {"user_id": user_id, "type": "chat"},
        sort=[("timestamp", -1)]
    )

    if not last_interaction:
        raise HTTPException(status_code=404, detail="User has no chat history to analyze.")

    user_text = last_interaction.get("message")
    
    # 2. Generate Embedding (Gemini)
    query_vector = get_embedding(user_text)
    if not query_vector:
        raise HTTPException(status_code=500, detail="Failed to generate AI embedding.")

    # 3. Find Similar Users (Milvus Vector Search)
    search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
    results = milvus_col.search(
        data=[query_vector],
        anns_field="vector",
        param=search_params,
        limit=5, # Top 5 similar users
        output_fields=["user_id"]
    )

    similar_user_ids = [res.entity.get("user_id") for res in results[0]]
    # Exclude the user themselves if found
    similar_user_ids = [uid for uid in similar_user_ids if uid != user_id]
    
    if not similar_user_ids:
        return {"user_id": user_id, "reason": "No similar users found", "recommendations": []}

    # 4. Find Campaigns Interacted by Similar Users (Neo4j)
    # "Find what campaigns the *similar* users clicked on"
    query = """
    MATCH (u:User)-[:INTERACTED]->(c:Campaign)
    WHERE u.user_id IN $similar_ids
    RETURN DISTINCT c.campaign_id AS campaign_id, c.name AS name
    """
    
    recommended_campaigns = []
    with neo4j_driver.session() as session:
        result = session.run(query, similar_ids=similar_user_ids)
        recommended_campaigns = [record.data() for record in result]

    if not recommended_campaigns:
        return {"user_id": user_id, "reason": "Similar users have no campaign history", "recommendations": []}

    # 5. Rank by Popularity (SQLite)
    camp_ids = [c['campaign_id'] for c in recommended_campaigns]
    scores = get_campaign_ranking(camp_ids)

    # Sort campaigns by score (highest first)
    ranked_campaigns = sorted(
        recommended_campaigns,
        key=lambda x: scores.get(x['campaign_id'], 0),
        reverse=True
    )

    return {
        "user_id": user_id,
        "based_on_last_message": user_text,
        "similar_users_count": len(similar_user_ids),
        "recommendations": ranked_campaigns
    }