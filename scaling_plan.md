<img width="1592" height="981" alt="data architecture" src="https://github.com/user-attachments/assets/08dec0d2-6dfb-498e-a554-b81e940c42b5" />

# Scaling Plan: From Prototype to 10M+ Users

This document outlines the strategic roadmap to evolve the current **Python-based prototype** into a **production-grade distributed system** capable of handling 10 million daily active users (DAU) and sub-100ms latency.

## 1. Introduction: The "Build vs. Buy" Shift
The current prototype prioritizes **simplicity** by using local file ingestion, sequential Python scripts, and in-memory caching. To scale, we must shift to **event-driven architecture** and **managed services**.

---

## 2. Ingestion Scaling (Introducing Kafka)

### Current Bottleneck
*   **Prototype:** Reads local JSON files sequentially.
*   **Limit:** Cannot handle real-time data streams or spikes in traffic (e.g., Black Friday). If the script crashes, data is lost.

### Production Solution: Apache Kafka
We will replace direct file reading with **Apache Kafka** to decouple producers from consumers.
*   **Why Kafka?**
    *   **Buffering:** Kafka acts as a shock absorber during traffic spikes, ensuring databases (Mongo/Milvus) aren't overwhelmed.
    *   **Parallelism:** We can deploy multiple consumer groups. One group writes to MongoDB (archival), while another processes Embeddings for Milvus simultaneously.
    *   **Replayability:** If the embedding service fails, we can replay the topic from the last committed offset.

---

## 3. Orchestration Scaling (Introducing Airflow)

### Current Bottleneck
*   **Prototype:** A single `etl.py` script runs everything (Ingest -> Embed -> Load).
*   **Limit:** If the embedding step fails, the entire pipeline stops. There is no visibility into retries, historical runs, or dependencies.

### Production Solution: Apache Airflow
We will decompose `etl.py` into a Directed Acyclic Graph (DAG) managed by **Airflow**.
*   **Why Airflow?**
    *   **Dependency Management:** Airflow ensures the "Analytics Aggregation" task only runs *after* data is successfully loaded into Neo4j.
    *   **Backfilling:** Easily re-process historical data if we change our embedding model (e.g., upgrading from Gemini `embedding-001` to `002`).
    *   **Alerting:** Integrated Slack/PagerDuty alerts when a specific task fails.

---

## 4. Latency Optimization (Introducing Redis)

### Current Bottleneck
*   **Prototype:** Calculates recommendations on-the-fly (Query Milvus -> Query Neo4j -> Rank).
*   **Limit:** This "Read-Path" computation takes 200-500ms. With 10M users, this will crash the API.

### Production Solution: Redis (Look-Aside Cache)
We will implement a **Cache-Aside pattern** using Redis.
*   **Strategy:**
    1.  **Check Redis First:** `GET recs:{user_id}`. (Latency: <5ms)
    2.  **Cache Miss:** If empty, perform the Milvus+Neo4j lookup.
    3.  **Write Back:** Store the result in Redis with a TTL (Time To Live) of 60 seconds.
*   **Impact:** 95% of requests will be served directly from memory, bypassing the heavy database queries entirely.

---

## 5. Database Scaling Strategies

### Milvus (Vector Search)
*   **Sharding:** Shard the collection based on `user_id` hash across multiple nodes.
*   **Index Optimization:** Switch from `IVF_FLAT` (brute force) to `HNSW` (Hierarchical Navigable Small World) graphs for faster search at the cost of higher RAM usage.
*   **Read Replicas:** Deploy read-only nodes to handle high QPS from the recommendation API.

### Neo4j (Graph)
*   **Causal Clustering:** Deploy Neo4j in a cluster structure. Writes go to the Core Leader, while Reads are load-balanced across Read Replicas.
*   **Data Pruning:** Archive interactions older than 1 year to cold storage (S3/Parquet) to keep the active graph traversal fast.

---

## 6. Cost Efficiency
*   **Tiered Storage:** Move raw logs from MongoDB (expensive SSDs) to S3/Data Lake (cheap object storage) after 30 days.
*   **Spot Instances:** Run the Batch ETL pipeline (Airflow workers) on AWS Spot Instances to reduce compute costs by up to 70%.
