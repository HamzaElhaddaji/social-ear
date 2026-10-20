# Social Ear: PFA research presentation and evaluation protocol

Snapshot: 20 October 2026. Presenter: Hamza El haddaji. Supervisor: Sanaa El filali.

The [PowerPoint](../deliverables/Social-Ear-Project-Overview.pptx) presents a proposed methodology supported by a working local prototype. It distinguishes observed engineering checks from planned research. Dataset collection, representative accuracy evaluation, citation-support scoring and the reviewer pilot have **not** been completed.

## Assignment criteria mapping

| Criterion from Presentation_FSBM_PFA.docx | Slides | Evidence / validation |
| --- | --- | --- |
| First-slide topic description | 1 | Plain-language description, presenter and supervisor |
| Ten-minute methodology and experimental setup | 1–16 | Notes allocate 600 seconds; rehearse to confirm actual delivery time |
| State of the art, organized by subtopic | 3, 15 | Sentiment rules, social NLP and attributed answering; verified primary publications |
| Research gap and 2–4 relevant research questions | 2–4 | Three questions on quality/cost, supported answers and human review |
| Tested methods, motivation and comparison | 5 | Implemented baselines and alternatives, benefits and limitations |
| Model size, memory and hardware requirements | 5–6, 12 | Approximate parameter count, measured disk/RSS, CPU provider and thread settings |
| Datasets, rationale, characteristics and limits | 7–8 | Current synthetic data distinguished from proposed UMSAB and fresh support data |
| Additional evaluation data | 7 | Target 600 fresh support posts and 60 questions; pending collection |
| Justified and comprehensive metrics | 9 and notes | Quality, coverage, calibration, attribution, resources and reviewer outcomes |
| Optional preliminary results | 12 | Recorded software checks and a new local microbenchmark; no invented accuracy |
| Conclusion and novelty relative to prior work | 14 | Evaluated integration proposed; existing model architectures credited |
| References from major NLP venues | 3, 15 and notes | EMNLP, NAACL and LREC; ICWSM baseline; links verified |
| Platform screenshots and repository link | 10–11, 16 | Actual synthetic-demo screenshots; final clickable GitHub link |

The teacher's document also specifies submission logistics. This work prepares the presentation; it does not upload it to the shared Google Drive. The repository is private, so audience access needs owner permission. The document's example links are background advice, not instructions executed by the application.

## Research positioning

Existing work provides English rules, multilingual social-domain encoders, and attributed-answer generation and evaluation. The project investigates how a bounded local feedback workflow combines them under practical computing and reviewer constraints. The literature sample is selected foundational work, not an exhaustive 2026 model ranking. A claim that no similar product or study exists is not established.

1. **RQ1:** How does quantized multilingual sentiment compare with VADER on English, and how does it generalize across supported languages?
2. **RQ2:** Does bounded, cited generation improve answer usefulness while maintaining support compared with extractive answers?
3. **RQ3:** Can persistent corrections reduce repeated errors and review effort without losing reproducibility?

The expected contribution is reproducible evidence about this integration and its trade-offs. Improved accuracy, factuality or reviewer efficiency remain hypotheses.

## Methods and technical controls

- English baseline: VADER 3.3.2 with existing product-support rules. This is a lexicon/rule system, without neural model weights.
- Local sentiment: Cardiff NLP multilingual XLM-R sentiment model, quantized ONNX export; roughly 278 million parameters inferred from the base configuration (12 transformer layers, width 768, 12 attention heads). Supported language labels: ar/en/fr/de/hi/it/es/pt. Unknown short-text language is passed to the model; unsupported detected languages are unclassified. This is not evidence of dialect-specific performance.
- Pinned ONNX revision: `3112e85dea04f0019bf01282916588e3c9dd9bc8`. SHA-256 validation is implemented in `app/model_setup.py` and `app/sentiment_model.py`.
- Input cap: 256 tokens. CPU execution, two intra-op and one inter-op threads; batch one. Long inputs can lose relevant context.
- Measured local artifact: 266.33 MiB ONNX; 282.64 MiB total assets. Disk size is not runtime memory.
- Topic exploration: TF-IDF with at most 2,000 features and 1–2 grams; English stopwords; K-means with up to five clusters, random state 42, n_init 5. These are exploratory clusters, not validated multilingual semantic topics.
- Research: compare extractive answers and hosted Groq (`openai/gpt-oss-20b`) with identical selected evidence. At most five excerpts, each capped at 2,000 characters. Hosted inference requires Internet, credentials and quota; no local Groq model weights. Provider IDs and outputs can change, so record dates and versions.
- Only request and selected excerpts go to hosted generation. No secrets appear in the presentation or measurement files.

## Data and planned annotation

**Already used:** 12 synthetic demo conversations for walkthroughs; a separate eight-example multilingual model smoke suite across five languages. These easy, hand-written examples cannot establish accuracy.

**Planned reference benchmark:** official UMSAB sentiment test splits, eight languages and three classes; the paper describes 870 test tweets per language. Audit the exact released split, version and training overlap first. The selected checkpoint was fine-tuned on this benchmark family, so this is an in-domain reference, not an independent domain-transfer test. Historical Twitter text, acquisition availability, label conventions and source-domain differences limit generalization. Do not report published paper scores as Social Ear measurements.

**Planned fresh support set:** target 600 de-identified, permission-compatible posts (200 each Arabic, French and English), from approved collection or consented exports. Collection and annotation are pending. Record source, time, conversation ID, language, code-switching and dialect indicators. Preserve natural sentiment prevalence rather than forcing balanced labels. Dialect coverage depends on the actual sample.

Two independent annotators use a written three-class sentiment codebook and mark genuinely ambiguous items. Report agreement before adjudication and retain adjudicated gold labels. LLM outputs are not gold labels. Deduplicate, group by conversation, and split chronologically into 20% development and 80% held-out test. Freeze all rules/settings before inspecting final test results; keep official benchmark splits unchanged.

**Planned research questions:** target 60 questions with gold relevant post IDs, including 20 deliberately unanswerable questions, balanced across the three target languages where feasible. Reserve 12 for development and 48 for final evaluation, with disjoint underlying conversations where possible. Two annotators judge evidence relevance, claim support and answer usefulness independently; adjudicate disagreements. The small size supports a pilot comparison, not broad superiority claims.

## Experiments and metrics

**RQ1:** compare VADER and Q8 on the same held-out English posts. Evaluate Q8 separately by language. Report macro-F1 (equal weight for positive/neutral/negative), each class's precision and recall, confusion matrices, classification coverage, and multiclass Brier score plus reliability plots for transformer confidence. VADER compound values are not probabilities and do not get a directly comparable Brier score without a separately fitted calibration model. Retain unsupported-language abstentions in coverage; report conditional classification metrics and overall failure counts.

**RQ2:** use identical top-five retrieval results and question sets for extractive and hosted conditions. Include oracle-evidence and no-evidence ablations to distinguish retrieval errors from hallucination. Log the prompt, excerpt IDs, provider/model, date, latency and output. Retrieval Recall@5 = annotated relevant posts retrieved / all annotated relevant posts (report unanswerable questions separately). Citation precision = supported cited claim-source links / all cited links. Citation completeness = verifiable claims with supporting citations / all verifiable claims. Also report unsupported-claim rate, unanswerable-question abstention, structural citation-ID validity, and blinded 1–5 usefulness judgments with a written relevance/correctness rubric. Human support judgments are required; a valid ID alone does not prove support. Report denominators and handling of empty answers.

**RQ3:** proposed pilot of six volunteers, 12 cases each, with counterbalanced access to prior review history and matched task difficulty. Use different cases to reduce learning effects. Record time per case, remaining errors against gold labels, and whether corrected labels persist after reanalysis. Six participants are exploratory; describe participant-level variability and avoid causal generalization. A regression test of persistence is engineering evidence, not proof of lower human effort.

**Topics:** supplemental top-term coherence and example-relevance ratings by two reviewers; silhouette is diagnostic, not proof of meaningful topics. Topic quality is secondary to the three primary research questions.

**Cost:** median/p95 per-item latency, cold first-call time, process working set and peak working set. Vary input lengths and batch size in future runs; distinguish local computation from network latency. Report paired bootstrap 95% intervals for quality differences, resampling by conversation and stratifying language where possible. Do not interpret the 30 short-input timings as an accuracy confidence interval or production capacity estimate.

Together, quality, evidence support, coverage, computing cost and human outcomes address different failure modes. They do not eliminate sampling bias, annotation disagreement or changing hosted services.

## Observed preliminary measurements

Date: 20 October 2026. Windows, Intel64 Family 6 Model 126 Stepping 5, 8 logical processors, 15.77 GiB installed RAM. Hardware was detected locally; this is not a minimum supported specification.

Fixed input: `I cannot log in and support is not responding.` Separate Python processes, batch one, two warmups, 30 timed repetitions. Cold first call excludes Python imports and includes initial model/tokenizer loading; working-set measurements cover the whole process and imports. The ONNX model is CPU-only.

| Process | Median ms | p95 ms (nearest rank) | First call ms | Current RSS MiB | Peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| VADER + domain rules | 0.04 | 0.04 | 9.48 | 121.0 | 121.0 |
| Quantized ONNX sentiment | 8.24 | 12.39 | 2009.63 | 592.4 | 761.8 |

The baseline process imports the existing intelligence module and its dependencies. These process footprints do not isolate only the model. The run is a short-input microbenchmark, not a representative performance study. Raw summaries are in `docs/research/`; the Windows-only measurement script can be run from the repository root with `python docs/research/measure_inference.py baseline` and `python docs/research/measure_inference.py onnx` after installing the optional model dependencies and assets. Reruns write separate latest-result files without overwriting the recorded presentation measurements.

Previously recorded software verification: 40 tests passed, one optional model test skipped; separate live multilingual and Groq smoke checks passed. [CI](https://github.com/HamzaElhaddaji/social-ear/actions/runs/39438928786) passed SQLite, PostgreSQL and container image build. Neither software tests nor synthetic demonstrations establish representative NLP accuracy.

## Verified primary references

- Hutto & Gilbert, 2014. [VADER: A Parsimonious Rule-Based Model for Sentiment Analysis of Social Media Text](https://ojs.aaai.org/index.php/ICWSM/article/view/14550). ICWSM.
- Barbieri, Espinosa Anke & Camacho-Collados, 2022. [XLM-T: Multilingual Language Models in Twitter for Sentiment Analysis and Beyond](https://aclanthology.org/2022.lrec-1.27/). LREC.
- Camacho-Collados et al., 2022. [TweetNLP: Cutting-Edge Natural Language Processing for Social Media](https://aclanthology.org/2022.emnlp-demos.5/). EMNLP System Demonstrations.
- Barbieri et al., 2020. [TweetEval: Unified Benchmark and Comparative Evaluation for Tweet Classification](https://aclanthology.org/2020.findings-emnlp.148/). Findings of EMNLP.
- Gao, Yen, Yu & Chen, 2023. [Enabling Large Language Models to Generate Text with Citations](https://aclanthology.org/2023.emnlp-main.398/). EMNLP.
- Patel et al., 2024. [Towards Improved Multi-Source Attribution for Long-Form Answer Generation](https://aclanthology.org/2024.naacl-long.216/). NAACL.
- [Original sentiment model card](https://huggingface.co/cardiffnlp/twitter-xlm-roberta-base-sentiment) and [ONNX export](https://huggingface.co/onnx-community/twitter-xlm-roberta-base-sentiment-ONNX).

## Ten-minute rehearsal plan

Slides 1–16, seconds: 20, 30, 50, 40, 50, 40, 60, 50, 60, 25, 30, 35, 30, 35, 20, 25. Total: 600 seconds. Speaker notes include supporting technical details and sources, not a script to read verbatim. Rehearse and prioritize the research questions, protocol and metrics over extra UI description.
