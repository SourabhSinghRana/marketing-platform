# Pipeline Failure & Reliability Strategy

In a distributed multi-database system, data consistency is the biggest challenge. Below is our strategy for detecting and handling failures.
<img width="1504" height="759" alt="airflow_pipeline_design" src="https://github.com/user-attachments/assets/6c91f498-e652-4dce-a09a-1f68eca3e15e" />

## 🛡️ 1. Airflow Orchestration & Sanity Checks
We propose a robust Airflow DAG structure to ensure data integrity across all systems.

### Pipeline 1: Micro-Batch Loading
*   **Frequency:** Every 10 minutes.
*   **Task:** Loads raw logs into MongoDB and aggregates metrics to BigQuery.
*   **Failure Handling:** If this fails, the batch is retried 3 times before moving to a Dead Letter Queue (DLQ).

### Pipeline 2: MongoDB Sanity Check
*   **Task:** Verifies that recent `user_id`s in MongoDB match the expected format and are not null.
*   **Action:** If data is corrupt, stop downstream jobs and alert the Data Engineering team via Slack/PagerDuty.

### Pipeline 3: Neo4j Graph Integrity
*   **Task:** "Orphan Node Detection". Checks if there are `(:Interaction)` relationships pointing to non-existent `(:Campaign)` nodes.
*   **Action:** Automatically flag these records for review.

### Pipeline 4: Milvus Vector Validation
*   **Task:** Randomly sample 100 vectors and verify they are not zero-vectors (all zeros) and dimensions match (768).
*   **Action:** If >5% of vectors are invalid, trigger a rollback of the latest embedding batch.

## 🔄 2. Error Handling in Ingestion (Current Prototype)
*   **Retry Logic:** The Python script implements exponential backoff for API calls (Google Gemini).
*   **Fallback Mechanism:** If the AI API is down, we generate "dummy" vectors to keep the pipeline flowing (soft failure), ensuring the system doesn't crash entirely.

## 🔍 3. Monitoring & Observability
*   **Latency Tracking:** We log the `start_time` and `end_time` of every batch.

*   **Data Lineage:** Each record in Neo4j/Milvus retains the original `interaction_id` from MongoDB for full traceability.

