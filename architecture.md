# System Architecture

<img width="1592" height="981" alt="data architecture" src="https://github.com/user-attachments/assets/ca3b43a3-22b0-4681-82af-f399aee66cc3" />

## Design Philosophy
The architecture follows the **Command Query Responsibility Segregation (CQRS)** pattern implicitly:
*   **Write Path:** Optimized for high throughput ingestion (MongoDB).
*   **Read Path:** Optimized for specific query patterns (Graph traversal, Vector search).

## Component Breakdown

### 1. Data Ingestion Layer
*   **Prototype:** Python scripts reading local JSON.
*   **Production:** Kafka Producers sending clickstream events to topics (`user_clicks`, `user_chats`). Kafka Consumers decouple the high-velocity ingestion from the database write load.

### 2. Storage Layer (The Polyglot Approach)
Instead of forcing all data into one database, we use the best tool for each job:
*   **MongoDB:** Handles the schema variability of chat logs.
*   **Milvus:** Selected over PGVector for its dedicated indexing capabilities and ability to scale to billions of vectors.
*   **Neo4j:** Selected over SQL JOINs because finding "Users similar to User A who liked Item B" involves multiple hops that are O(1) in Graph but O(N) in SQL.

### 3. API Layer
*   **FastAPI:** Chosen for its asynchronous capabilities, allowing it to query Milvus and Neo4j in parallel to reduce latency.

## Trade-offs
| Feature | Prototype Decision | Production Plan |
| :--- | :--- | :--- |
| **Orchestration** | Python Script (Sequential) | Airflow DAGs (Parallel + Retries) |
| **Streaming** | Direct File Read | Apache Kafka |
| **Caching** | In-Memory | Redis Cluster |

| **Security** | Local `.env` file | Hashicorp Vault / AWS Secrets Manager |
