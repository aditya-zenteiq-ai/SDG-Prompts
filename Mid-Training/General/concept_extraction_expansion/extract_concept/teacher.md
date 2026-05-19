You are a knowledge synthesis system. You will be given a passage of text and a single concept extracted from it.
The passage below may be an excerpt from a longer document. Extract concepts that are meaningfully present and at least partially explained in this passage. 
Do not extract concepts that are merely mentioned in passing without any accompanying explanation or context.
Use this passage as your primary source. Where the passage provides clear framing or explanation, follow it precisely. Where the passage is suggestive but incomplete, you may extend the reasoning conservatively — but do not contradict or ignore what the passage does say.

Your task:
1. Write a one-paragraph summary of the passage capturing its core argument or purpose.
2. Extract the most important concepts from the passage. A concept is any significant
   idea, principle, term, process, relationship, or mechanism discussed in the text.
   Focus on abstract and technical concepts rather than proper nouns, people, or locations.
   Extract between {target_concepts_range} concepts. Prefer precision over exhaustiveness.

Return your response as JSON only, with no additional text:
{
  "summary": "<one paragraph summary>",
  "concepts": ["concept1", "concept2", ...]
}
