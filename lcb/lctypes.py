"""LeetCode's runtime types (ListNode / TreeNode / Node) plus (de)serialisers
that speak LeetCode's JSON-ish testcase format."""
from __future__ import annotations

from collections import deque
from typing import Any, List, Optional


class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

    def __repr__(self):
        return f"ListNode({to_list(self)})"


class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

    def __repr__(self):
        return f"TreeNode({to_tree_list(self)})"


class Node:
    """Graph node (clone-graph) / N-ary tree node share this name on LeetCode."""

    def __init__(self, val=0, neighbors=None, children=None):
        self.val = val
        self.neighbors = neighbors if neighbors is not None else []
        self.children = children if children is not None else []


# ---------- builders ----------

def to_linked_list(values: Optional[List[Any]]) -> Optional[ListNode]:
    if not values:
        return None
    head = cur = ListNode(values[0])
    for v in values[1:]:
        cur.next = ListNode(v)
        cur = cur.next
    return head


def to_list(head: Optional[ListNode], limit: int = 100_000) -> List[Any]:
    out = []
    while head is not None and len(out) < limit:
        out.append(head.val)
        head = head.next
    if head is not None:
        raise ValueError("linked list appears to be cyclic / too long")
    return out


def to_tree(values: Optional[List[Any]]) -> Optional[TreeNode]:
    if not values or values[0] is None:
        return None
    root = TreeNode(values[0])
    q = deque([root])
    i = 1
    while q and i < len(values):
        node = q.popleft()
        if i < len(values) and values[i] is not None:
            node.left = TreeNode(values[i])
            q.append(node.left)
        i += 1
        if i < len(values) and values[i] is not None:
            node.right = TreeNode(values[i])
            q.append(node.right)
        i += 1
    return root


def to_tree_list(root: Optional[TreeNode]) -> List[Any]:
    if root is None:
        return []
    out, q = [], deque([root])
    while q:
        node = q.popleft()
        if node is None:
            out.append(None)
            continue
        out.append(node.val)
        q.append(node.left)
        q.append(node.right)
    while out and out[-1] is None:
        out.pop()
    return out


# ---------- type-driven conversion ----------

def from_lc(value: Any, lc_type: str) -> Any:
    """Convert a JSON-decoded LeetCode input into Python objects per metaData type."""
    t = lc_type.replace(" ", "")
    if t in ("ListNode",):
        return to_linked_list(value)
    if t in ("TreeNode",):
        return to_tree(value)
    if t in ("ListNode[]", "list<ListNode>"):
        return [to_linked_list(v) for v in value]
    if t in ("TreeNode[]", "list<TreeNode>"):
        return [to_tree(v) for v in value]
    if t in ("character", "char") and isinstance(value, str):
        return value
    return value


def to_lc(value: Any) -> Any:
    """Convert a Python return value back into LeetCode's JSON shape."""
    if isinstance(value, ListNode):
        return to_list(value)
    if isinstance(value, TreeNode):
        return to_tree_list(value)
    if isinstance(value, (list, tuple)):
        return [to_lc(v) for v in value]
    if isinstance(value, set):
        return sorted(to_lc(v) for v in value)
    if isinstance(value, dict):
        return {k: to_lc(v) for k, v in value.items()}
    return value
