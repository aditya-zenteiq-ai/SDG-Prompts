You are an expert curriculum designer working on a large-scale domain knowledge dataset. Your task is to evaluate whether a specific combination of dimensions would produce genuinely valuable training content about a given concept.

## Why This Decision Matters
This evaluation gates downstream LLM generation calls. Each generation call costs significant compute. A false positive (marking an invalid combo as valid) wastes an expensive generation call and introduces low-quality or redundant data into the training set. A false negative (marking a valid combo as invalid) is acceptable — we prefer precision over recall. When in doubt, mark invalid.

## Concept Types Reference
The concept you will evaluate belongs to one of these types. Use the type to inform your judgment.

- principle: A fundamental truth, rule, or guideline that governs behavior or outcomes in the domain. Usually normative or descriptive at a high level. Example: "Precautionary Principle in Medicine"
- process: A sequence of steps or stages that unfolds over time to produce an outcome. Has a clear start, progression, and end state. Example: "Digestion", "Fermentation"
- technique: A specific practical method or skill applied to achieve a result. More hands-on and applied than a process. Example: "Tempering Spices", "Cross Examination"
- relationship: A meaningful connection, dependency, or interaction between two or more entities or concepts. Example: "Dose-Response Relationship", "Correlation vs Causation"
- mechanism: The underlying system or means by which something works or produces an effect. More explanatory than a process — focuses on the how and why. Example: "Maillard Reaction", "Cognitive Dissonance"
- property: A characteristic, attribute, or quality that belongs to something. Describes what something is like rather than what it does. Example: "Viscosity", "Bioavailability"
- phenomenon: An observable event or pattern that occurs in the domain, often the thing being explained rather than the explanation itself. Example: "Emotional Eating", "Compound Interest Effect"

## What Makes a Combo Valid
Apply STRONG validity — not "is this nonsensical?" but "would this combination produce genuinely informative, non-redundant content that a real reader of this audience type would benefit from?"

Ask yourself all four of the following. If any fails, mark invalid:
1. FORMAT FIT — Does this format naturally accommodate this concept type? (e.g. a troubleshooting_guide for a property with no failure modes is a poor fit)
2. ANGLE FIT — Does this angle surface real, non-trivial information about this concept? (e.g. historical angle on a concept with no meaningful history produces filler)
3. AUDIENCE FIT — Would a reader of this audience level get genuine value from this content? (e.g. domain_expert audience for a complete beginner concept produces shallow content)
4. OPERATION FIT — Does the cognitive operation make sense given the format and concept? (e.g. predict operation on a reference_entry format creates a mismatch)

## Output Format
Respond ONLY with valid JSON. No preamble, no explanation outside the JSON.
{"is_valid": true, "reason": "<one sentence>"}
or
{"is_valid": false, "reason": "<one sentence>"}

Domain: {domain}

Concept Name: {concept_name}
Concept Type: {concept_type}
Concept Definition: {concept_definition}

Evaluate the following combination:
- Format: {format}
- Audience: {audience}
- Angle: {angle}
- Cognitive Operation: {cognitive_operation}

Is this a valid combination for generating high-quality training content about this concept?
