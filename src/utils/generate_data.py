import json
import random
import os
from faker import Faker
from datetime import datetime, timedelta

# Configuration
NUM_USERS = 20        # Reduced to ensure higher density of connections
NUM_CAMPAIGNS = 10
NUM_INTERACTIONS = 50 # Reduced from 200 to 50 to avoid API Rate Limits
DATA_DIR = "data"

fake = Faker()
Faker.seed(42)

os.makedirs(DATA_DIR, exist_ok=True)

def generate_users():
    users = []
    for i in range(1, NUM_USERS + 1):
        users.append({
            "user_id": f"u_{i:03d}",
            "name": fake.name(),
            "email": fake.email(),
            "age": random.randint(18, 60),
            "signup_date": fake.date_this_year().isoformat()
        })
    return users

def generate_campaigns():
    campaigns = []
    themes = ["Summer Sale", "AI Personalization", "Cloud Storage Promo", 
            "Gaming Laptop Deal", "Fitness Tracker", "Crypto Wallet", 
            "Home Automation", "VR Headset Launch", "DevOps Course", "5G Data Plan"]
    
    for i in range(1, NUM_CAMPAIGNS + 1):
        theme = themes[i-1]
        campaigns.append({
            "campaign_id": f"c_{i:03d}",
            "name": f"{theme} 2024",
            "category": "Technology",
            "budget": random.randint(1000, 50000),
            "status": "Active"
        })
    return campaigns

def generate_interactions(users, campaigns):
    interactions = []
    intents = [
        "I am looking for a new laptop for coding.",
        "Do you have any deals on cloud storage?",
        "I want to track my runs and sleep.",
        "Is there a discount on VR headsets?",
        "How do I automate my home lights?",
        "Tell me about the new crypto wallet features.",
        "I need a fast internet plan for gaming.",
        "Are there any courses for learning Kubernetes?",
        "I want to buy a gift for a tech enthusiast.",
        "Show me the latest summer tech gadgets."
    ]

    for _ in range(NUM_INTERACTIONS):
        user = random.choice(users)
        campaign = random.choice(campaigns)
        # 70% chance of a chat, 30% chance of just a click
        is_chat = random.random() > 0.3
        
        interaction = {
            "interaction_id": fake.uuid4(),
            "user_id": user["user_id"],
            "campaign_id": campaign["campaign_id"],
            "timestamp": fake.date_time_between(start_date='-30d', end_date='now').isoformat(),
            "type": "chat" if is_chat else "click"
        }

        if is_chat:
            interaction["message"] = random.choice(intents)
        
        interactions.append(interaction)
        
    return interactions

def save_json(data, filename):
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"[SUCCESS] Generated {len(data)} records in {filepath}")

if __name__ == "__main__":
    print("[INFO] Starting Data Generation...")
    
    users = generate_users()
    campaigns = generate_campaigns()
    interactions = generate_interactions(users, campaigns)
    
    save_json(users, "users.json")
    save_json(campaigns, "campaigns.json")
    save_json(interactions, "interactions.json")
    
    print("[INFO] Data Generation Complete.")