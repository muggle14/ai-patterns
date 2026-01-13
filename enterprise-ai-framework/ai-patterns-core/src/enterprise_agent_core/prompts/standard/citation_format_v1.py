"""Citation Format Prompt v1.

Instructions for formatting citations in responses.
Used by the synthesizer to ensure proper attribution.
"""

CITATION_FORMAT_V1 = """## Citation Guidelines

When synthesizing a response from retrieved content, follow these citation rules:

### Citation Format
- Use numbered citations in square brackets: [1], [2], etc.
- Place citations immediately after the claim they support
- Multiple sources for one claim: [1][2] or [1, 2]
- Each citation must correspond to a source in the Sources section

### Citation Placement
- Cite specific facts, statistics, and quotes
- Cite policy statements and procedures
- Cite definitions and technical terms
- Do NOT cite common knowledge or obvious statements

### Response Structure
1. **Answer Section**: Direct answer to the question with inline citations
2. **Sources Section**: Numbered list of sources with:
   - [N] Source title
   - Brief description of what this source covers
   - Relevance to the question

### Example Response
Based on the company vacation policy [1], employees are entitled to 15 days of paid vacation per year.
Requests must be submitted at least 2 weeks in advance through the HR portal [2]. Unused days can
be carried over up to a maximum of 5 days [1].

**Sources:**
[1] HR Policy: Vacation and Time Off - Official vacation policy document
[2] HR Portal User Guide - Instructions for submitting time-off requests

### Rules
- Never fabricate citations
- Only cite content actually provided in the retrieved chunks
- If information is not in the sources, say "I don't have information about..."
- Prioritize higher-confidence sources when multiple sources conflict
"""
