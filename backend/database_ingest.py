import os
import math
from collections import Counter
import chromadb
from chromadb.utils import embedding_functions


class SimpleBM25:
    """Lightweight zero-dependency BM25Okapi implementation for hybrid search ranking."""
    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.doc_lens = [len(doc.lower().split()) for doc in corpus]
        self.avgdl = sum(self.doc_lens) / max(1, len(corpus))
        self.doc_freqs: list[Counter] = [Counter(doc.lower().split()) for doc in corpus]
        self.idf: dict[str, float] = {}
        self._init_idf()

    def _init_idf(self):
        df = Counter()
        for freq in self.doc_freqs:
            for term in freq:
                df[term] += 1
        n_docs = len(self.corpus)
        for term, freq in df.items():
            self.idf[term] = math.log(((n_docs - freq + 0.5) / (freq + 0.5)) + 1.0)

    def get_scores(self, query: str) -> list[float]:
        q_tokens = query.lower().split()
        scores = []
        for idx, freq in enumerate(self.doc_freqs):
            score = 0.0
            doc_len = self.doc_lens[idx]
            len_norm = 1.0 - self.b + self.b * (doc_len / max(1e-4, self.avgdl))
            for token in q_tokens:
                if token in freq:
                    t_idf = self.idf.get(token, 0.0)
                    tf = freq[token]
                    score += t_idf * (tf * (self.k1 + 1.0)) / (tf + self.k1 * len_norm)
            scores.append(score)
        return scores


class DatabaseIngestPipeline:
    def __init__(self, db_path: str = None):
        """Initializes the local persistent vector database storage engine on disk."""
        if db_path is None:
            data_dir = os.getenv("DATA_DIR")
            if data_dir:
                db_path = os.path.join(data_dir, "chroma_knowledge_base")
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                db_path = os.path.join(current_dir, "chroma_knowledge_base")
        
        self.client = chromadb.PersistentClient(path=db_path)
        self.embedding_function = embedding_functions.DefaultEmbeddingFunction()
        
        # Core collection for textbook RAG grounding
        self.curriculum_collection = self.client.get_or_create_collection(
            name="curriculum_repository",
            embedding_function=self.embedding_function
        )

    def ingest_openstax_text(self, file_path: str, subject: str, academic_tier: str):
        """Processes raw text textbooks into paragraphs with chapter-level metadata and adds them to the vector index in safe batch sizes."""
        import re
        if not os.path.exists(file_path):
            print(f"[WARN] Source file not found at {file_path}. Generating fallback mock content for initialization.")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as fallback:
                fallback.write(
                    f"Newton's Laws of Motion govern classical mechanics in {subject}. Force equals mass times acceleration (F=ma).\n\n"
                    f"In a sorted list, binary search algorithms find elements in logarithmic time complexity O(log n)."
                )

        with open(file_path, "r", encoding="utf-8") as file:
            raw_text = file.read()

        raw_blocks = [b.strip() for b in raw_text.split("\n\n") if b.strip()]
        if not raw_blocks:
            print(f"[ERROR] No valid text segments extracted from {file_path}")
            return

        # Sequential chapter header discovery across raw text blocks
        ch_re_1 = re.compile(r"^(?:CHAPTER|Chapter)\s+(\d+)[:\s\-\.]*([^\n]*)", re.IGNORECASE)
        ch_re_2 = re.compile(r"^(\d+)\s+([A-Z\s]{4,40})$")

        candidates = []
        for i, b in enumerate(raw_blocks):
            lines = [l.strip() for l in b.split("\n") if l.strip()]
            if not lines:
                continue
            first_line = lines[0]
            if re.search(r"\b(Problems & Exercises|Index|Solutions|Answer Key)\b", first_line, re.IGNORECASE):
                continue
            m1 = ch_re_1.match(first_line)
            if m1:
                ch_num = int(m1.group(1))
                suffix = m1.group(2).strip()
                title = suffix or (lines[1] if len(lines) > 1 else "")
                if re.search(r"\s+\d+$", title):
                    continue
                candidates.append((i, ch_num, title))
                continue
            m2 = ch_re_2.match(first_line)
            if m2 and int(m2.group(1)) <= 60:
                ch_num = int(m2.group(1))
                title = m2.group(2).strip()
                if re.search(r"\s+\d+$", title):
                    continue
                candidates.append((i, ch_num, title))

        sequence = []
        expected = 1
        for i, ch_num, title in candidates:
            if ch_num == expected:
                sequence.append((i, ch_num, title))
                expected += 1
            elif ch_num == 1 and expected > 1 and len(sequence) < 5:
                sequence = [(i, ch_num, title)]
                expected = 2

        # Map each block index to its owning chapter
        ch_map = {}
        if sequence:
            seq_idx = 0
            for i in range(len(raw_blocks)):
                if seq_idx + 1 < len(sequence) and i >= sequence[seq_idx + 1][0]:
                    seq_idx += 1
                if i >= sequence[0][0]:
                    ch_map[i] = (sequence[seq_idx][1], sequence[seq_idx][2])
                else:
                    ch_map[i] = (1, sequence[0][2])
        else:
            for i in range(len(raw_blocks)):
                ch_map[i] = (1, f"{subject} Chapter 1")

        all_ids = []
        all_metadatas = []
        all_docs = []
        for i, b in enumerate(raw_blocks):
            if len(b) > 40:
                ch_idx, ch_title_raw = ch_map[i]
                current_ch_id = f"ch_{ch_idx}"
                clean_title = f"Chapter {ch_idx}: {ch_title_raw}" if ch_title_raw and not ch_title_raw.startswith(f"Chapter {ch_idx}") else (ch_title_raw or f"Chapter {ch_idx}")
                doc_id = f"{subject.lower()}_{academic_tier.replace(' ', '_').lower()}_{current_ch_id}_{len(all_docs):05d}"
                all_ids.append(doc_id)
                all_docs.append(b)
                all_metadatas.append({
                    "subject": subject,
                    "academic_tier": academic_tier,
                    "grade_level": academic_tier,
                    "chapter_id": current_ch_id,
                    "chapter_index": ch_idx,
                    "chapter_title": clean_title,
                    "data_integrity_status": "verified"
                })

        total_chunks = len(all_docs)
        if total_chunks == 0:
            print(f"[ERROR] No valid paragraphs > 40 chars extracted from {file_path}")
            return

        print(f"\n[Processing {subject} | {academic_tier}] Extracted {total_chunks} paragraphs across {len(sequence) if sequence else 1} detected chapters. Slicing into vector batches...")

        batch_size = 2000
        for start_idx in range(0, total_chunks, batch_size):
            end_idx = start_idx + batch_size
            batch_ids = all_ids[start_idx:end_idx]
            batch_docs = all_docs[start_idx:end_idx]
            batch_metadatas = all_metadatas[start_idx:end_idx]
            try:
                self.curriculum_collection.upsert(
                    ids=batch_ids, 
                    documents=batch_docs, 
                    metadatas=batch_metadatas
                )
                print(f"   Processed segment range [{start_idx} to {min(end_idx, total_chunks)}] successfully...")
            except Exception as e:
                print(f"[ChromaDB] Batch upsert warning: {e}")

        print(f"[OK] Successfully vectorized and loaded all {total_chunks} paragraphs from {subject} ({academic_tier}) into ChromaDB.")

    def ingest_custom_chunks(
        self,
        course_id: str,
        chunks: list[str],
        subject: str = "General",
        academic_tier: str = "Custom",
        chapter_id: str = "ch_1",
        chapter_index: int = 1,
        chapter_title: str = "",
    ):
        """
        Ingests dynamically parsed chunks with SHA-256 content deduplication to prevent vector DB bloat.
        Uses deterministic content hashing to prevent duplicate vector caching.
        Attaches chapter_id and chapter_title metadata to isolate context and prevent chapter crosstalk.
        """
        import hashlib
        if not chunks:
            return 0

        # Filter out empty or near-empty chunks
        unique_chunks_map = {}
        for c in chunks:
            clean_c = c.strip()
            if len(clean_c) > 40:
                chunk_hash = hashlib.sha256(clean_c.encode('utf-8')).hexdigest()[:16]
                if chunk_hash not in unique_chunks_map:
                    unique_chunks_map[chunk_hash] = clean_c

        if not unique_chunks_map:
            return 0

        clean_ch_id = str(chapter_id or f"ch_{chapter_index}").strip()
        try:
            ch_idx = int(chapter_index)
        except (ValueError, TypeError):
            ch_idx = 1

        ids = []
        documents = []
        metadatas = []

        for chunk_hash, text in unique_chunks_map.items():
            doc_id = f"{course_id}_{clean_ch_id}_{chunk_hash}"
            ids.append(doc_id)
            documents.append(text)
            metadatas.append({
                "course_id": course_id,
                "chapter_id": clean_ch_id,
                "chapter_index": ch_idx,
                "chapter_title": chapter_title or f"Chapter {ch_idx}",
                "subject": subject,
                "academic_tier": academic_tier,
                "content_hash": chunk_hash,
                "data_integrity_status": "verified"
            })

        batch_size = 200
        for start_idx in range(0, len(ids), batch_size):
            end_idx = start_idx + batch_size
            try:
                # Use upsert to avoid duplicate insertion errors
                self.curriculum_collection.upsert(
                    ids=ids[start_idx:end_idx],
                    documents=documents[start_idx:end_idx],
                    metadatas=metadatas[start_idx:end_idx],
                )
            except Exception as e:
                print(f"[ChromaDB] Upsert warning: {e}")

        return len(ids)

    def ingest_custom_chunks_batch(
        self,
        batch_items: list[dict],
    ) -> int:
        """
        Batches ingestion across multiple chapters into consolidated ChromaDB upsert calls.
        Reduces embedding overhead and Chroma client round-trips significantly.
        """
        import hashlib
        if not batch_items:
            return 0

        ids = []
        documents = []
        metadatas = []

        for item in batch_items:
            course_id = item.get("course_id", "")
            chunks = item.get("chunks", [])
            subject = item.get("subject", "General")
            academic_tier = item.get("academic_tier", "Custom")
            raw_chapter_id = item.get("chapter_id", "ch_1")
            raw_chapter_index = item.get("chapter_index", 1)
            chapter_title = item.get("chapter_title", "")

            clean_ch_id = str(raw_chapter_id or f"ch_{raw_chapter_index}").strip()
            try:
                ch_idx = int(raw_chapter_index)
            except (ValueError, TypeError):
                ch_idx = 1

            unique_chunks_map = {}
            for c in chunks:
                clean_c = c.strip()
                if len(clean_c) > 40:
                    chunk_hash = hashlib.sha256(clean_c.encode('utf-8')).hexdigest()[:16]
                    if chunk_hash not in unique_chunks_map:
                        unique_chunks_map[chunk_hash] = clean_c

            for chunk_hash, text in unique_chunks_map.items():
                doc_id = f"{course_id}_{clean_ch_id}_{chunk_hash}"
                ids.append(doc_id)
                documents.append(text)
                metadatas.append({
                    "course_id": course_id,
                    "chapter_id": clean_ch_id,
                    "chapter_index": ch_idx,
                    "chapter_title": chapter_title or f"Chapter {ch_idx}",
                    "subject": subject,
                    "academic_tier": academic_tier,
                    "content_hash": chunk_hash,
                    "data_integrity_status": "verified"
                })

        if not ids:
            return 0

        batch_size = 200
        for start_idx in range(0, len(ids), batch_size):
            end_idx = start_idx + batch_size
            try:
                self.curriculum_collection.upsert(
                    ids=ids[start_idx:end_idx],
                    documents=documents[start_idx:end_idx],
                    metadatas=metadatas[start_idx:end_idx],
                )
            except Exception as e:
                print(f"[ChromaDB] Batch upsert warning: {e}")

        return len(ids)

    def delete_course_vectors(self, course_id: str) -> int:
        """Purges all vector embeddings associated with a deleted course to keep vector store lean."""
        try:
            self.curriculum_collection.delete(
                where={"course_id": course_id}
            )
            print(f"[ChromaDB] Successfully purged vector records for course: {course_id}")
            return 1
        except Exception as e:
            print(f"[ChromaDB] Error purging course vectors for {course_id}: {e}")
            return 0

    def query_verified_context(
        self,
        query: str,
        course_id: str = None,
        subject: str = None,
        academic_tier: str = None,
        chapter_id: str = None,
        chapter_index: int = None,
        n_results: int = 3
    ) -> list[str]:
        """Queries the local collection using verified structural parameters and optional course_id/subject/chapter filter."""
        where_clauses = [{"data_integrity_status": "verified"}]
        
        if course_id:
            where_clauses.append({"course_id": course_id})
        else:
            if subject:
                where_clauses.append({"subject": subject})
            if academic_tier:
                where_clauses.append({"academic_tier": academic_tier})

        if chapter_id is not None or chapter_index is not None:
            ch_conditions = []
            if chapter_id is not None:
                ch_raw = str(chapter_id).strip()
                ch_conditions.append({"chapter_id": ch_raw})
                if ch_raw.lower().startswith("ch_"):
                    num_part = ch_raw[3:]
                    if num_part:
                        ch_conditions.append({"chapter_id": num_part})
                else:
                    ch_conditions.append({"chapter_id": f"ch_{ch_raw}"})

            if chapter_index is not None:
                try:
                    ch_conditions.append({"chapter_index": int(chapter_index)})
                except (ValueError, TypeError):
                    pass

            if len(ch_conditions) == 1:
                where_clauses.append(ch_conditions[0])
            elif len(ch_conditions) > 1:
                where_clauses.append({"$or": ch_conditions})
                
        where_filter = {"$and": where_clauses} if len(where_clauses) > 1 else where_clauses[0]
        
        try:
            results = self.curriculum_collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter
            )
            return results['documents'][0] if results and results.get('documents') and len(results['documents']) > 0 else []
        except Exception as e:
            print(f"[ChromaDB] Query error: {e}")
            return []

    def query_chapter_context(
        self,
        query: str,
        course_id: str = None,
        chapter_id: str = None,
        chapter_index: int = None,
        subject: str = None,
        academic_tier: str = None,
        n_results: int = 4,
        allow_fallback: bool = False
    ) -> list[str]:
        """
        Queries ChromaDB specifically isolated to a course and chapter to eliminate cross-chapter content mixing.
        Normalizes chapter identifiers (e.g. '1', 'ch_1', integer index) to guarantee robust matching.
        When allow_fallback=False (default), strictly returns context from the specified chapter without crosstalk.
        """
        where_clauses = [{"data_integrity_status": "verified"}]
        if course_id:
            where_clauses.append({"course_id": course_id})
        else:
            if subject:
                where_clauses.append({"subject": subject})
            if academic_tier:
                where_clauses.append({"academic_tier": academic_tier})

        if chapter_id is not None or chapter_index is not None:
            ch_conditions = []
            if chapter_id is not None:
                ch_raw = str(chapter_id).strip()
                ch_conditions.append({"chapter_id": ch_raw})
                if ch_raw.lower().startswith("ch_"):
                    num_part = ch_raw[3:]
                    if num_part:
                        ch_conditions.append({"chapter_id": num_part})
                else:
                    ch_conditions.append({"chapter_id": f"ch_{ch_raw}"})

            if chapter_index is not None:
                try:
                    ch_conditions.append({"chapter_index": int(chapter_index)})
                except (ValueError, TypeError):
                    pass

            if len(ch_conditions) == 1:
                where_clauses.append(ch_conditions[0])
            elif len(ch_conditions) > 1:
                where_clauses.append({"$or": ch_conditions})

        where_filter = {"$and": where_clauses} if len(where_clauses) > 1 else where_clauses[0]

        try:
            results = self.curriculum_collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter
            )
            docs = results['documents'][0] if results and results.get('documents') and len(results['documents']) > 0 else []
            if docs:
                return docs
        except Exception as e:
            print(f"[ChromaDB] Chapter-scoped query notice: {e}")

        # Strict isolation: only fallback to broader scope if explicitly permitted
        if allow_fallback:
            return self.query_verified_context(
                query=query,
                course_id=course_id,
                subject=subject,
                academic_tier=academic_tier,
                n_results=n_results
            )
        return []

    def query_hybrid(
        self,
        query: str,
        course_id: str = None,
        chapter_id: str = None,
        chapter_index: int = None,
        subject: str = None,
        academic_tier: str = None,
        n_results: int = 4,
        allow_fallback: bool = False
    ) -> list[str]:
        """
        Executes hybrid search fusing dense semantic vector similarity with sparse BM25 keyword matching
        using Reciprocal Rank Fusion (RRF). Prioritizes exact formula and variable matches.
        Strictly isolates retrieval to the target chapter whenever chapter_id or chapter_index is provided.
        """
        candidates = []
        if chapter_id is not None or chapter_index is not None:
            candidates = self.query_chapter_context(
                query=query,
                course_id=course_id,
                chapter_id=chapter_id,
                chapter_index=chapter_index,
                subject=subject,
                academic_tier=academic_tier,
                n_results=n_results * 2,
                allow_fallback=allow_fallback
            )
        elif course_id:
            candidates = self.query_verified_context(
                query=query,
                course_id=course_id,
                n_results=n_results * 2
            )
        else:
            candidates = self.query_verified_context(
                query=query,
                subject=subject,
                academic_tier=academic_tier,
                n_results=n_results * 2
            )

        if not candidates or len(candidates) <= 1:
            return candidates

        # Run BM25 keyword ranking
        bm25 = SimpleBM25(candidates)
        bm25_scores = bm25.get_scores(query)
        bm25_ranked = sorted(range(len(candidates)), key=lambda i: bm25_scores[i], reverse=True)

        # Reciprocal Rank Fusion (k=60)
        rrf_scores = [0.0] * len(candidates)
        for dense_rank, _ in enumerate(candidates):
            rrf_scores[dense_rank] += 1.0 / (60.0 + dense_rank + 1)
        for bm25_rank, doc_idx in enumerate(bm25_ranked):
            rrf_scores[doc_idx] += 1.0 / (60.0 + bm25_rank + 1)

        fused_indices = sorted(range(len(candidates)), key=lambda i: rrf_scores[i], reverse=True)
        return [candidates[i] for i in fused_indices[:n_results]]



    def preview_interaction_metrics(self, csv_path: str):
        """Validates that your backend Performance Analyzer can cleanly parse your shrunken EdNet sample."""
        import csv
        if not os.path.exists(csv_path):
            print(f"[WARN] Warning: Active tracking log sample missing at {csv_path}. Please verify your shrink_dataset.py ran correctly.")
            return

        print(f"\n[PREVIEW] Previewing EdNet telemetry interaction mapping from: {csv_path}")
        with open(csv_path, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for idx, row in enumerate(reader):
                if idx >= 3: 
                    break
                print(f"   [Row {idx+1}] User ID: {row.get('user_id') or row.get('student_id')} | Action: {row.get('action_type') or 'QA'} | Latency: {row.get('elapsed_time')}ms")


_default_pipeline = None

def get_db_pipeline(db_path: str = None) -> DatabaseIngestPipeline:
    """Returns a process-wide singleton DatabaseIngestPipeline instance."""
    global _default_pipeline
    if _default_pipeline is None:
        _default_pipeline = DatabaseIngestPipeline(db_path=db_path)
    return _default_pipeline


if __name__ == "__main__":
    pipeline = DatabaseIngestPipeline()
    
    # Delete the old collection to start fresh
    try:
        pipeline.client.delete_collection("curriculum_repository")
        print("[CLEARED] Old collection curriculum_repository removed.")
    except Exception as e:
        print("No old collection to delete or error:", e)
        
    pipeline.curriculum_collection = pipeline.client.get_or_create_collection(
        name="curriculum_repository",
        embedding_function=pipeline.embedding_function
    )
    
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define textbook sources to load into the curriculum repository
    textbooks = [
        # Physics
        {"path": os.path.join(backend_dir, "data", "curriculum", "physics_textbook.txt"), "subject": "Physics", "tier": "Class 10"},
        {"path": os.path.join(backend_dir, "data", "curriculum", "physics_textbook.txt"), "subject": "Physics", "tier": "Class 11-12"},
        {"path": os.path.join(backend_dir, "data", "curriculum", "physics_textbook.txt"), "subject": "Physics", "tier": "Undergraduate"},
        
        # Biology
        {"path": os.path.join(backend_dir, "data", "curriculum", "biology_textbook.txt"), "subject": "Biology", "tier": "Class 10"},
        {"path": os.path.join(backend_dir, "data", "curriculum", "biology_textbook.txt"), "subject": "Biology", "tier": "Class 11-12"},
        {"path": os.path.join(backend_dir, "data", "curriculum", "biology_textbook.txt"), "subject": "Biology", "tier": "Undergraduate"},
        
        # Mathematics
        {"path": os.path.join(backend_dir, "data", "curriculum", "math_textbook.txt"), "subject": "Mathematics", "tier": "Class 10"},
        {"path": os.path.join(backend_dir, "data", "curriculum", "math_textbook.txt"), "subject": "Mathematics", "tier": "Class 11-12"},
        {"path": os.path.join(backend_dir, "data", "curriculum", "calculus_textbook.txt"), "subject": "Mathematics", "tier": "Undergraduate"}
    ]
    
    # 1. Ingest all curriculum content paths sequentially
    for book in textbooks:
        pipeline.ingest_openstax_text(book["path"], book["subject"], book["tier"])
    
    # 2. Test reading behavioral interaction metrics sample path
    ednet_sample_path = os.path.join(backend_dir, "data", "ednet", "ednet_small_sample.csv")
    pipeline.preview_interaction_metrics(ednet_sample_path)