# Scaling Plan: From Prototype to 10M+ Users

This document outlines the strategic roadmap to evolve the current **Python-based prototype** into a **production-grade distributed system** capable of handling 10 million daily active users (DAU).
<img width="1587" height="972" alt="data_architecture" src="https://github.com/user-attachments/assets/24640110-49d2-4bfd-a99e-611575cf85d0" />

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

## 3. Latency Optimization (Redis)
*Goal: Sub-100ms API Response Time.*

*   **Pattern:** Cache-Aside.
*   **Flow:**
    1.  API checks `Redis` for `recs:{user_id}`.
    2.  **Hit (5ms):** Return cached JSON.
    3.  **Miss:** Query Milvus + Neo4j $\rightarrow$ Compute Rank $\rightarrow$ Save to Redis (TTL 60s) $\rightarrow$ Return.
*   **Scale:** Redis Cluster mode enables horizontal scaling of memory to store millions of active user sessions.

---

## 4. Database Scaling

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


