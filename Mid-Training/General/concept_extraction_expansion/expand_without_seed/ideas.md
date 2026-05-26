# Concept Expansion Pipeline — Handoff Document
> Purpose: Full context for an agent tasked with designing prompts for the concept expansion pipeline. Read this entire document before designing any prompt.

---

## 1. Goal

We are building a **domain-specific midtraining dataset** for LLMs. One model will be trained per domain. The training objective is to shift the model's knowledge distribution toward a target domain — not general pretraining from scratch.

**Target data volume:** 2B–10B tokens per domain.  
**Current seed data:** ~20M input tokens total, growing.  
**Required amplification:** ~1,000x–5,000x from seed data.

This amplification cannot come from rephrasing or paraphrasing — that produces semantic duplicates which hurt training. It must come from generating **genuinely different content** about the same concepts by varying multiple independent dimensions simultaneously.

---

## 2. Domains

The following domains are in scope:

| Domain | Notes |
|---|---|
| Astrology | |
| Cooking | |
| Diets | |
| Household | |
| Humour | |
| Indian_Cooking | |
| Law | Use web search / RAG to ground generation |
| Medicine | Use web search / RAG to ground generation |
| Mental Health | |
| first_aid | |
| Multilingual | Deferred — will translate to Indic languages post-generation |

---

## 3. Available Models (Locally Hosted on 512 TPUs)

| Model | Identifier Used in Pipeline |
|---|---|
| Qwen3 32B | `qwen3_32b` |
| Gemma4 31B | `gemma4` |
| DeepSeek V3.2 | `deepseek` |
| Qwen3.5 122B | `Qwen/Qwen3.5-122B-A10B` |
| Qwen3 Guard | `qwen3_guard` |

These models are invoked via an internal pipeline API. Prompts must be designed with these models in mind — no OpenAI or Anthropic API calls.

---

## 4. Pipeline Overview

The full pipeline has three tiers:

```
TIER 0 — Seed Texts (raw domain corpus)
    ↓
TIER 1 — Concept Extraction (grounded, close to seed text)
    ↓
TIER 2 — Concept Expansion (high volume, uses broader model knowledge)
```

Tier 1 produces structured concept objects.  
Tier 2 is the primary source of training volume and is the focus of this document.

---

## 5. Tier 1 — Concept Extraction (FINALIZED)

### Input
- A seed text passage
- Domain name
- Target concepts range (varies by domain, see Section 7)

### Output
Structured JSON:
```json
{
  "domain": "<domain>",
  "summary": "<one paragraph summary of the passage>",
  "concepts": [
    {
      "name": "<concept name in natural language>",
      "definition": "<one sentence definition as the passage frames it>",
      "type": "<one of the types below>"
    }
  ]
}
```

### Concept Types
| Type | Definition |
|---|---|
| principle | A fundamental truth, rule, or guideline governing behavior or outcomes. Usually normative or descriptive at a high level. |
| process | A sequence of steps unfolding over time to produce an outcome. Has clear start, progression, and end state. |
| technique | A specific practical method or skill applied to achieve a result. More hands-on than a process. |
| relationship | A meaningful connection, dependency, or interaction between two or more entities or concepts. |
| mechanism | The underlying system by which something works or produces an effect. Focuses on the how and why. |
| property | A characteristic or attribute that belongs to something. Describes what it is like rather than what it does. |
| phenomenon | An observable event or pattern in the domain, often the thing being explained rather than the explanation. |

### Grounding Rules
- Use the passage as the primary source.
- Where the passage provides clear framing, follow it precisely.
- Where the passage is suggestive but incomplete, extend conservatively.
- Do not contradict or ignore what the passage says.
- Do not extract concepts merely mentioned in passing without explanation.

### Target Concepts Range by Domain
```python
DOMAIN_RANGE_MAP = {
    "Medicine":        "6-9",
    "Law":             "6-9",
    "Mental Health":   "6-9",
    "Diets":           "5-8",
    "Indian_Cooking":  "5-8",
    "Cooking":         "5-8",
    "Astrology":       "5-7",
    "Household":       "4-7",
    "first_aid":       "5-8",
    "Humour":          "4-6",
    "Multilingual":    "5-7",
}
```

---

## 6. Tier 2 — Concept Expansion (PROMPTS NEEDED)

This is the high-volume generation tier. For each extracted concept, we generate many pieces of content by varying across multiple dimensions. The goal is semantic diversity — each generated piece should cover meaningfully different ground.

### Core Principle
Diversity comes from sampling across **independent dimensions simultaneously**. Varying only one dimension produces near-duplicates. Varying multiple at once forces genuinely different information to surface.

### The Five Dimensions

#### Dimension 1 — Format
How the content is structured:

| ID | Format | Description |
|---|---|---|
| F01 | tutorial | Step-by-step instructional |
| F02 | dialogue | Two-person conversation |
| F03 | faq | Question and answer pairs |
| F04 | case_study | Real scenario walkthrough |
| F05 | commentary | Expert opinion and analysis |
| F06 | reference_entry | Encyclopedic definition and elaboration |
| F07 | myth_vs_fact | Structured misconception correction |
| F08 | analogy_explainer | Concept explained through extended analogy |
| F09 | troubleshooting_guide | Problem → diagnosis → solution structure |
| F10 | narrative | Story-driven explanation |

#### Dimension 2 — Audience
Who the content is written for:

| ID | Audience | Description |
|---|---|---|
| A01 | complete_beginner | No prior knowledge assumed |
| A02 | informed_layperson | General education, no domain expertise |
| A03 | practitioner | Working professional in the domain |
| A04 | domain_expert | Deep technical knowledge |
| A05 | skeptic | Questioning or resistant to the concept |
| A06 | student | Learning the domain formally |
| A07 | caregiver_or_helper | Relevant for medicine, mental health, first aid |

#### Dimension 3 — Angle
What aspect of the concept is being explored:

| ID | Angle | Description |
|---|---|---|
| G01 | mechanistic | How it works internally |
| G02 | historical | How it developed or was discovered |
| G03 | failure_modes | When and why it goes wrong |
| G04 | edge_cases | Boundary conditions and exceptions |
| G05 | practical_limits | Real-world constraints and caveats |
| G06 | common_misuse | How people apply it incorrectly |
| G07 | underlying_theory | Foundational principles behind it |
| G08 | interdependencies | What other concepts it relies on or affects |

#### Dimension 4 — Cognitive Operation
What mental task the content demands from the reader:

| ID | Operation | Description |
|---|---|---|
| O01 | explain | Build understanding |
| O02 | apply | Use in a specific context |
| O03 | critique | Evaluate strengths and weaknesses |
| O04 | compare | Contrast with a related concept |
| O05 | troubleshoot | Diagnose a problem involving the concept |
| O06 | predict | Reason about outcomes using the concept |
| O07 | synthesize | Combine with other concepts to reason about something new |

#### Dimension 5 — Scenario
A concrete real-world situation in which the concept is relevant. **This dimension is not enumerable** — scenarios are concept-specific and domain-specific and must be generated separately (see Section 8).

---

## 7. Tier 2 Execution Strategy

### Two-Step Process

**Step 1 — Combo Validity Check (Fixed Dimensions)**

Take the cross-product of Format × Audience × Angle × Cognitive Operation for each concept. This gives a large number of combos. For each combo, call the LLM with:
- The concept (name, definition, type)
- The domain
- The specific combo (format, audience, angle, operation)

Ask the model to return a `valid` or `invalid` flag, with a brief reason.

**Validity definition (important):** A combo is valid not just if it is non-nonsensical, but if it would produce **genuinely informative, non-redundant content** about this concept. This is a high bar — use strong validity, not weak validity.

All combo validity calls are fully parallelizable.

**Step 2 — Scenario Generation**

Separately, for each concept + domain, ask the model to generate N concrete real-world scenarios where the concept is meaningfully relevant. These are generated independently of the fixed dimension combos. Scenarios then feed into generation calls as their own dimension axis.

### Generation Call

Once valid combos (from Step 1) and scenarios (from Step 2) are ready, fire one generation call per valid combo and one per scenario. These are all parallelizable.

**Important:** Combo selection and content generation are intentionally separated into different calls. Do not combine them into one prompt. This gives:
- Retryability (failed generation doesn't lose the combo)
- Inspectability (valid combo list can be audited before generation)
- Parallelism (all generation calls for a concept run simultaneously)

### Deduplication
Post-generation deduplication will be applied (MinHash + embedding similarity filtering). Prompts are not the sole deduplication mechanism, but should minimize obvious semantic overlap.

---

## 8. Prompts Needed (What This Document Is Requesting)

Three prompts need to be designed:

### Prompt A — Combo Validity Check
**Input variables:**
- `{domain}` — domain name
- `{concept_name}` — natural language concept name
- `{concept_definition}` — one sentence definition
- `{concept_type}` — one of the seven types
- `{format}` — one value from the Format dimension
- `{audience}` — one value from the Audience dimension
- `{angle}` — one value from the Angle dimension
- `{cognitive_operation}` — one value from the Cognitive Operation dimension

**Expected output:** JSON with `valid` (boolean) and `reason` (one sentence).

**Key design consideration:** The model must apply strong validity — not just "is this nonsensical" but "would this combination produce genuinely informative, non-redundant content about this concept in this domain". Be explicit about this in the prompt.

---

### Prompt B — Scenario Generation
**Input variables:**
- `{domain}` — domain name
- `{concept_name}` — natural language concept name
- `{concept_definition}` — one sentence definition
- `{concept_type}` — one of the seven types

**Expected output:** JSON list of N concrete real-world scenarios (suggest N=8–12). Each scenario should be a 1–2 sentence description of a specific situation where this concept is meaningfully at play. Scenarios must be domain-grounded.

**Key design consideration:** Scenarios should be maximally diverse from each other — different settings, different actors, different stakes. The model should not generate variations of the same scenario.

---

### Prompt C — Content Generation
**Input variables:**
- `{domain}` — domain name
- `{concept_name}` — natural language concept name
- `{concept_definition}` — one sentence definition
- `{concept_type}` — one of the seven types
- One of:
  - `{format}` + `{audience}` + `{angle}` + `{cognitive_operation}` (from a valid Step 1 combo)
  - `{scenario}` (from Step 2 scenario generation)

**Expected output:** A piece of content, free-form text, of reasonable length (300–800 words). No JSON wrapping needed.

**Key design considerations:**
- The model should draw on its **broader knowledge** of the concept, not just the seed text. Seed text is not passed in.
- Content must be domain-grounded. The domain is passed as a variable and should steer the framing, vocabulary, and examples.
- For Law and Medicine domains, outputs will be additionally grounded via RAG/web search at call time.
- Output must be self-contained and coherent as a standalone piece.
- Do not repeat the combo parameters mechanically at the start of the output. Just generate the content.

---

## 9. What NOT to Do

- Do not pass the seed text into Tier 2 generation prompts. Tier 2 draws on broader model knowledge.
- Do not combine validity check and content generation into one call.
- Do not ask the model to enumerate all valid combos in one call — it over-generates and is inconsistent. Each combo is checked individually.
- Do not use rephrasing or paraphrasing as a generation strategy — this produces semantic duplicates.
- Do not use a weak validity definition ("is this nonsensical?") — use strong validity ("would this produce genuinely informative content?").

---

## 10. Summary of All Prompt Variables

| Variable | Used In | Source |
|---|---|---|
| `{domain}` | A, B, C | Set at pipeline invocation |
| `{concept_name}` | A, B, C | Tier 1 extraction output |
| `{concept_definition}` | A, B, C | Tier 1 extraction output |
| `{concept_type}` | A, B, C | Tier 1 extraction output |
| `{format}` | A, C | Fixed dimension list (F01–F10) |
| `{audience}` | A, C | Fixed dimension list (A01–A07) |
| `{angle}` | A, C | Fixed dimension list (G01–G08) |
| `{cognitive_operation}` | A, C | Fixed dimension list (O01–O07) |
| `{scenario}` | C | Prompt B output |
