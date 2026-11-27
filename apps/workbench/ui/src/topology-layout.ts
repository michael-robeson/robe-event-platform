import dagre, { type EdgeLabel, type GraphLabel, type NodeLabel } from "@dagrejs/dagre";

export type TopologyNode = {
  id: string;
  kind: "infrastructure" | "service" | "topic" | "subscription";
  name: string;
  status: string;
  declared: boolean;
  observed: boolean;
  details: Record<string, unknown>;
};

export type TopologyEdge = {
  id: string;
  source: string;
  target: string;
  relationship: string;
  evidence: string[];
  status: string;
};

export type Topology = { checked_at: string; nodes: TopologyNode[]; edges: TopologyEdge[] };

export const NODE_WIDTH = 180;
export const NODE_HEIGHT = 88;

export function layoutTopology(topology: Topology) {
  const infrastructure = topology.nodes.filter((node) => node.kind === "infrastructure");
  const nodes = topology.nodes.filter((node) => node.kind !== "infrastructure")
    .sort((left, right) => left.id.localeCompare(right.id));
  const nodeIds = new Set(nodes.map((node) => node.id));
  const graph = new dagre.graphlib.Graph<GraphLabel, NodeLabel, EdgeLabel>({ multigraph: true });
  graph.setGraph({ rankdir: "LR", ranksep: 50, nodesep: 45, edgesep: 25, marginx: 15, marginy: 15 });
  graph.setDefaultEdgeLabel(() => ({}));
  for (const node of nodes) graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });

  const hiddenDeclarations: TopologyEdge[] = [];
  const declaredDeliveries = topology.edges.filter((edge) =>
    edge.relationship === "delivers_to" && edge.evidence.includes("declared"));
  const declaredPushes = topology.edges.filter((edge) =>
    edge.relationship === "pushes_to" && edge.evidence.includes("declared"));
  const edges = topology.edges.filter((edge) => {
    if (edge.relationship === "contains") return false;
    const representedConsumption = edge.relationship === "consumes"
      && declaredDeliveries.some((delivery) => delivery.source === edge.target
        && declaredPushes.some((push) => push.source === delivery.target && push.target === edge.source));
    if (representedConsumption || edge.relationship === "dead_letter") {
      hiddenDeclarations.push(edge);
      return false;
    }
    return true;
  }).sort((left, right) => left.id.localeCompare(right.id))
    .map((edge) => {
      // A consumes declaration is service -> topic in the API, but the message flows toward the service.
      const source = edge.relationship === "consumes" ? edge.target : edge.source;
      const target = edge.relationship === "consumes" ? edge.source : edge.target;
      if (!nodeIds.has(source) || !nodeIds.has(target)) {
        throw new Error(`Topology relationship ${edge.id} references a missing node`);
      }
      const relationship = edge.relationship === "consumes" ? "consumed by"
        : edge.relationship === "dead_letter_policy" ? "dead-letter policy"
        : edge.relationship.replaceAll("_", " ");
      const status = edge.status === "available" ? "" : ` · ${edge.status.replaceAll("_", " ")}`;
      const evidence = edge.evidence.map((item) => item === "declared" ? "D" : item === "observed" ? "O" : item).join("+");
      const label = `${relationship} · ${evidence}${status}`;
      const description = `${relationship} · ${edge.evidence.join(" + ")}${status}`;
      graph.setEdge(source, target, {
        width: label.length * 7 + 16,
        height: 24,
        labelpos: "c",
      }, edge.id);
      return { edge, source, target, label, description };
    });

  dagre.layout(graph);
  return {
    infrastructure,
    hiddenDeclarations: hiddenDeclarations.sort((left, right) => left.id.localeCompare(right.id)),
    nodes: nodes.map((node) => {
      const position = graph.node(node.id);
      if (position.x === undefined || position.y === undefined) throw new Error(`No layout for ${node.id}`);
      return { node, position: { x: position.x - NODE_WIDTH / 2, y: position.y - NODE_HEIGHT / 2 } };
    }),
    edges: edges.map(({ edge, source, target, label, description }) => {
      const route = graph.edge(source, target, edge.id);
      if (!route.points || route.x === undefined || route.y === undefined) {
        throw new Error(`No layout for relationship ${edge.id}`);
      }
      return {
        edge, source, target, label, description,
        points: route.points,
        labelPosition: { x: route.x, y: route.y },
      };
    }),
  };
}
