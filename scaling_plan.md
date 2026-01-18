# Scaling Plan: 10M+ Users & Sub-100ms Latency

To evolve this prototype into a hyperscale platform, we will implement the following strategies.
<img width="1592" height="981" alt="data architecture" src="https://github.com/user-attachments/assets/08dec0d2-6dfb-498e-a554-b81e940c42b5" />

## 1. Database Scaling Strategies

### Milvus (Vector Search)
*   **Sharding:** We will shard the collection based on `user_id` hash.
*   **Index Optimization:** Switch from `IVF_FLAT` (brute force inside clusters) to `HNSW` (Hierarchical Navigable Small World) graphs for faster, albeit slightly more memory-intensive, search.
*   **Read Replicas:** Deploy read-only nodes to handle high QPS from the recommendation API.

### Neo4j (Graph)
*   **Causal Clustering:** Deploy Neo4j in a cluster with Read Replicas.
*   **Data Pruning:** Archive interactions older than 1 year to cold storage (S3/Parquet) to keep the active graph small and fast.

## 2. Latency Optimization (<100ms)

### The "Cache-First" Architecture
1.  **L1 Cache (Redis):** Store pre-computed recommendations.
    *   *Hit:* Return in 5ms.
    *   *Miss:* Compute via Milvus/Neo4j.
2.  **Async Computation:** Do not compute recommendations *during* the user request.
    *   Use a background worker (Celery/Kafka) to re-compute recommendations whenever a user interacts.
    *   The API simply fetches the latest pre-computed list from Redis.

## 3. Cost Efficiency
*   **Tiered Storage:** Move raw logs from MongoDB (expensive SSDs) to S3/Data Lake (cheap object storage) after 30 days.
*   **Spot Instances:** Run the Batch ETL pipeline (Airflow workers) on AWS Spot Instances to reduce compute costs by up to 70%.

*   **Quantization:** Use scalar quantization (SQ8) in Milvus to reduce vector size by 4x with minimal accuracy loss.
