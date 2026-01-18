# Scaling Plan: From Prototype to 10M+ Users

This document outlines the strategic roadmap to evolve the current **Python-based prototype** into a **production-grade distributed system** capable of handling 10 million daily active users (DAU).
<img width="1592" height="981" alt="data architecture" src="https://github.com/user-attachments/assets/08dec0d2-6dfb-498e-a554-b81e940c42b5" />

## 1. Introduction: Separation of Concerns
To handle 10M+ users, we must separate **Real-Time Ingestion** (sub-second latency) from **Batch Orchestration** (reliability & consistency).
*   **Real-Time Layer:** Handled by Apache Kafka.
*   **Management Layer:** Handled by Apache Airflow.

---

## 2. Real-Time Ingestion (Kafka Consumers)
*Goal: Decouple high-velocity user data from database write limits.*

### The "Fan-Out" Architecture
Instead of a single script, we will utilize **Kafka Consumer Groups** to process streams in parallel:

1.  **Topic:** `user_interactions`
2.  **Consumer Group A (Archival):** Reads raw JSON and bulk-writes to **MongoDB**.
3.  **Consumer Group B (Vectorization):** 
    *   Consumes message text.
    *   Calls Embedding API (Gemini).
    *   Writes vectors to **Milvus**.
    *   *Advantage:* If the Embedding API is slow, it only lags this specific consumer group, not the whole system.
4.  **Consumer Group C (Graph Builder):** 
    *   Extracts User/Campaign IDs.
    *   Updates relationships in **Neo4j**.

**Why this scales:**
*   **Backpressure Handling:** If traffic spikes (e.g., Black Friday), Kafka buffers the messages. The databases ingest at their own maximum speed without crashing.
*   **Fault Tolerance:** If the Neo4j consumer crashes, it restarts and resumes exactly from the last processed message offset.

---

## 3. Orchestration & Quality Assurance (Apache Airflow)
*Goal: Data Integrity and Analytical Aggregation (not real-time ingestion).*

As per our architecture design, Airflow is strictly used for **Micro-Batches** and **Sanity Checks**.

### Pipeline 1: Analytics Sync (Micro-Batch)
*   **Schedule:** Every 10 minutes.
*   **Task:** Aggregate interaction counts from Redis/Mongo and load them into **Google BigQuery**.
*   **Why:** BigQuery is optimized for analytical loads, not row-by-row streaming inserts.

### Pipeline 2: MongoDB Sanity Check
*   **Task:** Verify data freshness.
*   **Logic:** `SELECT count(*) FROM mongo_logs WHERE timestamp > NOW() - 1 hour`. If count is 0, alert "Ingestion Down".

### Pipeline 3: Graph Consistency Check
*   **Task:** Ensure Referential Integrity.
*   **Logic:** Check if any `:INTERACTED` relationship in Neo4j points to a missing `:Campaign` node. Flag data engineering team if discrepancies found.

### Pipeline 4: Vector Index Health
*   **Task:** Validate Milvus Index.
*   **Logic:** Perform a "dummy search" against Milvus to ensure the index is loaded and responsive.

---

## 4. Latency Optimization (Redis)
*Goal: Sub-100ms API Response Time.*

*   **Pattern:** Cache-Aside.
*   **Flow:**
    1.  API checks `Redis` for `recs:{user_id}`.
    2.  **Hit (5ms):** Return cached JSON.
    3.  **Miss:** Query Milvus + Neo4j $\rightarrow$ Compute Rank $\rightarrow$ Save to Redis (TTL 60s) $\rightarrow$ Return.
*   **Scale:** Redis Cluster mode enables horizontal scaling of memory to store millions of active user sessions.

---

## 5. Database Scaling

### Milvus (Vector DB)
*   **Sharding:** Partition collections by `user_id` hash.
*   **Query Nodes:** Separate "Query Nodes" (Read) from "Data Nodes" (Write) to ensure heavy ingestion doesn't slow down user searches.

### Neo4j (Graph DB)
*   **Read Replicas:** Use Causal Clustering. The API reads from Read Replicas, while Kafka writes to the Core Leader.

### Cost Control
*   **Hot/Cold Storage:**
    *   **Hot (Redis/Milvus):** Last 7 days of data.
    *   **Warm (Mongo/Neo4j):** Last 90 days.
    *   **Cold (S3/Data Lake):** Older than 90 days (managed via Airflow archiving jobs).
