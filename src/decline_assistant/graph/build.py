"""Assemble the StateGraph."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from decline_assistant.graph.deps import GraphDeps
from decline_assistant.graph.nodes import make_analyze, make_cluster, make_load, make_retrieve
from decline_assistant.graph.state import GraphState

NODE_ORDER: tuple[str, ...] = ("load", "cluster", "retrieve", "analyze")


def build_graph(deps: GraphDeps) -> CompiledStateGraph[GraphState, None, GraphState, GraphState]:
    graph: StateGraph[GraphState, None, GraphState, GraphState] = StateGraph(GraphState)
    graph.add_node("load", make_load(deps))
    graph.add_node("cluster", make_cluster(deps))
    graph.add_node("retrieve", make_retrieve(deps))
    graph.add_node("analyze", make_analyze(deps))
    previous = START
    for name in NODE_ORDER:
        graph.add_edge(previous, name)
        previous = name
    graph.add_edge(previous, END)
    return graph.compile(name="decline-code-assistant")
