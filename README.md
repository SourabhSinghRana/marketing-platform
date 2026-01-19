# AI-Driven Marketing Personalization Platform

## 📌 Overview
This project is a **scalable, multi-database data platform** designed to power real-time marketing personalization. It demonstrates a "Polyglot Persistence" architecture, unifying **Vector** (Milvus), **Graph** (Neo4j), **Document** (MongoDB), and **Analytical** (SQLite) databases to deliver hybrid retrieval recommendations.

## 🚀 Key Features
*   **Hybrid Retrieval:** Combines semantic search (Milvus) with knowledge graph traversal (Neo4j).
*   **GenAI Integration:** Uses Google Gemini to generate embeddings from user chat logs.
*   **Resilient Pipeline:** Includes retry logic, rate-limit handling, and error logging.
*   **Production-Ready Architecture:** Designed to scale from a local prototype to a Kafka/Airflow production environment.

## 📚 Documentation & Thought Process
Please review the following documents for deep dives into design choices and production strategies:

*   **[Architecture Design](architecture.md):** Detailed breakdown of the system design, explaining the trade-offs between this **Prototype** (Python scripts) and the **Production Vision** (Kafka/Airflow) shown in the diagram.
*   **[Scaling Plan (10M+ Users)](scaling_plan.md):** A roadmap for evolving this system to handle massive scale, introducing Kafka consumers, Redis caching, and database sharding.
*   **[Pipeline Failure Strategy](pipeline_failure_strategy.md):** How we handle data reliability, including Airflow sanity checks, retry logic, and error monitoring.

<img width="1587" height="972" alt="data_architecture" src="https://github.com/user-attachments/assets/e22f0115-5782-4092-ab48-217a6e12c732" />

<img width="1825" height="960" alt="data_modeling" src="https://github.com/user-attachments/assets/cea6cd28-28dd-45e8-a3b9-4d79d01040bb" />

## 🛠️ Tech Stack
*   **Language:** Python 3.9+
*   **API:** FastAPI
*   **Databases:** MongoDB, Neo4j, Milvus, SQLite
*   **Infrastructure:** Docker Compose
*   **AI Model:** Google Gemini `embedding-001`


## ⚙️ Setup & Installation

### 1. Prerequisites
*   Docker & Docker Compose
*   Python 3.9+
*   Google Gemini API Key ([Get one here](https://aistudio.google.com/))

### 2. Environment Setup
Create a `.env` file in the root directory:
```ini
GEMINI_API_KEY=your_api_key_here
MONGO_URI=mongodb://admin:password@localhost:27017/
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

## 🏃 How to Run (Step-by-Step)

Follow these commands in order from the project root terminal.

### Step 1: Start the Infrastructure
Spin up MongoDB, Neo4j, and Milvus containers.
```bash
docker-compose up -d
> ⏳ **Wait 60 seconds** after this command for Milvus to fully initialize.

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Generate Synthetic Data
Create dummy users, campaigns, and chat logs.
```bash
python src/utils/generate_data.py
```
*Expected Output:* `[SUCCESS] Generated ... records`

### Step 4: Run the ETL Pipeline
Ingest data, generate AI embeddings, and populate all databases.
```bash
python src/pipeline/etl.py
```
*Expected Output:* `Pipeline finished successfully in ... seconds`

### Step 5: Start the API Server
Launch the Hybrid Retrieval API.
```bash
uvicorn src.api.app:app --reload
```
*The server will start at `http://127.0.0.1:8000`*

---

## 🧪 How to Test

1.  Open your browser to the **Swagger UI**:  
    [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

2.  Click on the endpoint: **`GET /recommendations/{user_id}`**

3.  Click **"Try it out"**.

4.  Enter a User ID from the generated data (e.g., `u_001`, `u_005`).

5.  Click **"Execute"**.

### Sample Response
You will receive a JSON object containing the user's last message, similar users found via vector search, and campaigns ranked by popularity.

```json
{
  "user_id": "u_001",
  "based_on_last_message": "I need a fast internet plan for gaming.",
  "similar_users_count": 4,
  "recommendations": [
    {
      "campaign_id": "c_009",
      "name": "5G Data Plan"
    },
    {
      "campaign_id": "c_003",
      "name": "Cloud Storage Promo"
    }
  ]
}
```

---

## 📂 Project Structure

```text
├── data/                  # Generated JSON datasets
├── src/
│   ├── api/               # FastAPI application
│   ├── pipeline/          # ETL orchestration script
│   └── utils/             # Data generators & helpers
├── docker-compose.yml     # Database infrastructure
├── requirements.txt       # Python dependencies
└── README.md              # Documentation
```




