# SPDX-License-Identifier: AGPL-3.0-or-later
"""Deterministic dependency graph analysis with relationship semantics."""

from __future__ import annotations

import heapq
from collections.abc import Iterable

from .models import UserInputError


def find_cycle(nodes: Iterable[str], edges: Iterable[tuple[str, str]]) -> list[str] | None:
    """Return one stable cycle where each edge is prerequisite -> consumer."""
    adjacency = {node: [] for node in sorted(set(nodes))}
    for source, target in sorted(set(edges)):
        adjacency.setdefault(source, []).append(target)
        adjacency.setdefault(target, [])
    state: dict[str, int] = {node: 0 for node in adjacency}
    stack: list[str] = []
    positions: dict[str, int] = {}

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        positions[node] = len(stack)
        stack.append(node)
        for target in adjacency[node]:
            if state[target] == 0:
                cycle = visit(target)
                if cycle:
                    return cycle
            elif state[target] == 1:
                return stack[positions[target] :] + [target]
        stack.pop()
        positions.pop(node, None)
        state[node] = 2
        return None

    for node in sorted(adjacency):
        if state[node] == 0:
            cycle = visit(node)
            if cycle:
                return cycle
    return None


def stable_topological_order(nodes: Iterable[str], edges: Iterable[tuple[str, str]]) -> list[str]:
    """Sort dependency-first with lexical tie breaking."""
    node_set = set(nodes)
    adjacency = {node: [] for node in node_set}
    indegree = {node: 0 for node in node_set}
    for source, target in sorted(set(edges)):
        if source not in node_set or target not in node_set:
            continue
        adjacency[source].append(target)
        indegree[target] += 1
    queue = [node for node, degree in indegree.items() if degree == 0]
    heapq.heapify(queue)
    ordered: list[str] = []
    while queue:
        node = heapq.heappop(queue)
        ordered.append(node)
        for target in sorted(adjacency[node]):
            indegree[target] -= 1
            if indegree[target] == 0:
                heapq.heappush(queue, target)
    if len(ordered) != len(node_set):
        cycle = find_cycle(node_set, edges) or []
        raise UserInputError(f"Dependency cycle: {' -> '.join(cycle)}")
    return ordered
