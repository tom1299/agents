from langchain_core.tools import BaseTool


def contains_metadata_annotation(tool: BaseTool, annotation: str) -> bool:
    annotations = (tool.metadata or {}).get("mcp", {}).get("tool", {}).get("annotations", {})
    annotation_value = annotations.get(annotation)
    return annotation_value is not None and annotation_value == True


def read_only(tool: BaseTool) -> bool:
    read_only_hint_value = contains_metadata_annotation(tool, "read_only_hint")
    destructive_hint_value = contains_metadata_annotation(tool, "destructive_hint")
    return read_only_hint_value and not destructive_hint_value