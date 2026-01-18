# Architecture & System Design
<img width="1592" height="981" alt="data architecture" src="https://github.com/user-attachments/assets/114e5b47-acfa-4c2a-8114-d13be86f01eb" />

## 1. Overview: The "North Star" vs. The Prototype
This project demonstrates a **Multi-Database (Polyglot Persistence)** platform for AI-driven marketing. 

To satisfy the assignment requirements while demonstrating "Founding Engineer" foresight, this documentation distinguishes between:
1.  **Production Architecture (The Diagram):** The target state designed for 10M+ users, high availability, and sub-100ms latency.
2.  **Prototype Implementation (The Code):** A lightweight, container-optimized version submitted for this review.

---

## 2. Production Architecture (As seen in Diagram)
The architecture diagram provided in `architecture_diagram.png` illustrates the **Event-Driven Design** required for a production environment.

### Key Components:
*   **Ingestion:** **Apache Kafka** decouples high-velocity user streams from database writes. It handles backpressure during traffic spikes (e.g., Black Friday).
*   **Orchestration:** **Apache Airflow** manages micro-batch analytics, sanity checks, and data consistency jobs.
*   **Caching:** **Redis** serves as a Look-Aside cache to protect the downstream databases from high-frequency read queries.
*   **Analytics:** **Google BigQuery** handles massive-scale aggregations that would choke a transactional database.

---

## 3. Prototype Architecture (Current Implementation)
For the purpose of this Take-Home Assignment, I made conscious **Pragmatic Trade-offs** to keep the submission runnable, lightweight, and focused on core logic rather than infrastructure boilerplate.

### Architecture Comparison Matrix

| Component | Production (The Diagram) | Prototype (The Code) | Justification for Prototype |
| :--- | :--- | :--- | :--- |
| **Ingestion** | **Kafka Consumers** (Parallel Groups) | **Python Generator** (Sequential) | Removes the need for Zookeeper/Broker setup; easier to inspect data flow. |
| **Orchestration** | **Apache Airflow** (DAGs) | **`etl.py` Script** (Linear) | Reduces container footprint; avoids Airflow scheduler overhead for a single job. |
| **Caching** | **Redis Cluster** (Distributed) | **Python In-Memory** / Logic | Demonstrates the *logic* of caching without requiring a Redis container. |
| **Analytics** | **Google BigQuery** (Cloud) | **SQLite** (`analytics.db`) | Allows offline testing without requiring GCP credentials/costs. |
| **Databases** | **Mongo, Neo4j, Milvus** | **Mongo, Neo4j, Milvus** | **Kept the same.** These are the core requirements and run in Docker. |

---

## 4. Design Decisions: Polyglot Persistence
Instead of forcing all data into a single database (e.g., Postgres), I utilized specific stores for specific data shapes.

<img width="1825" height="960" alt="data_modeling" src="https://github.com/user-attachments/assets/ccf1dce8-5fba-4645-9b12-96bd64da5e33" />

### 🍃 MongoDB (Document Store)
*   **Role:** The "Source of Truth" for raw interaction logs.
*   **Why:** Chat logs are unstructured and variable. MongoDB allows us to ingest data without strict schema migration downtime.

### 👁️ Milvus (Vector Database)
*   **Role:** Semantic Similarity Engine.
*   **Why:** We need to find "Similar Users" based on chat context, not keywords. Milvus handles high-dimensional vectors (768-dim from Gemini) efficiently.

### 🕸️ Neo4j (Graph Database)
*   **Role:** Relationship Mapper.
*   **Why:** Answering *"Which campaigns did users similar to User A click?"* is a multi-hop traversal query.
    *   **SQL:** Requires expensive `JOIN` operations (O(N)).
    *   **Graph:** Uses pointer chasing (O(1)), making it exponentially faster for recommendation paths.

### 📊 SQLite (Analytics Mock)
*   **Role:** Ranking Engine.
*   **Why:** Stores pre-aggregated "Engagement Scores". We query this to rank the Neo4j results by popularity.

---

## 5. Data Flow (Hybrid Retrieval)
The API endpoint `GET /recommendations/{user_id}` implements a sophisticated 3-step retrieval logic:

1.  **Vector Step (Milvus):** 
    *   *Input:* User's last chat message.
    *   *Action:* Convert to Vector via Gemini AI -> Find Top 5 nearest neighbor Users.
    *   *Output:* `[User_B, User_C, User_D]`

2.  **Graph Step (Neo4j):**
    *   *Input:* List of Similar Users.
    *   *Action:* Traverse `(:User)-[:INTERACTED]->(:Campaign)` to find what they liked.
    *   *Output:* `[Campaign_X, Campaign_Y]`

3.  **Ranking Step (Analytics):**
    *   *Input:* List of Candidate Campaigns.
    *   *Action:* Sort by `total_interactions` from the Analytics DB.
    *   *Result:* The most relevant, high-performing campaign for that specific user context.


