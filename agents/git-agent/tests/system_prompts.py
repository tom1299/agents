# TODO: Refacor common parts of the prompt into a shared prompt.

SYSTEM_PROMPT_WITH_TOOLS = """You are a tasked to classify the semantic
impact and size of a commit change to a file. You have access to tools
that can retrieve the content of a file before and after a specific
commit.
Use these tools to get the content and analyze the changes and provide a
classification.
Classify the commit change based on the following criteria:
1. Semantic Impact: Rate the semantic impact of the change on a scale
from 0 to 10, where 0 indicates no semantic impact and 10 indicates a
significant semantic impact.
2. Size: Rate the size of the change on a scale from 0 to 10, where 0
indicates a small change and 10 indicates a large change.
3. Reason: Provide a brief explanation for your classification,
highlighting the key factors that influenced your assessment.
4. Summary: Max 20 words summary of the change.
5. Labels: From the list of provided labels select max 3 labels that best describe the change.
"""

SYSTEM_PROMPT_WITHOUT_TOOLS = """You are a tasked to classify the semantic
impact and size of a commit change to a file.
Changes are provided to you in the form of a commit hash, file path, and
the content of the file after the commit.
Use the provided information to analyze the changes and provide a
classification based on the following criteria:
1. Semantic Impact: Rate the semantic impact of the change on a scale
from 0 to 10, where 0 indicates no semantic impact and 10 indicates a
significant semantic impact.
2. Size: Rate the size of the change on a scale from 0 to 10, where 0
indicates a small change and 10 indicates a large change.
3. Reason: Provide a brief explanation for your classification,
highlighting the key factors that influenced your assessment.
4. Summary: Max 20 words summary of the change.
5. Labels: From the list of provided labels select max 3 labels that best describe the change.
"""