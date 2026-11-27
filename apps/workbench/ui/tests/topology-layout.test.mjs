import assert from "node:assert/strict";
import test from "node:test";
import { layoutTopology, NODE_HEIGHT, NODE_WIDTH } from "../src/topology-layout.ts";

const node = (id, kind) => ({ id, kind, name: id, status: "available", declared: true, observed: true, details: {} });
const edge = (source, target, relationship, evidence = ["declared"], status = "available") => ({
  id: `${source}|${relationship}|${target}`, source, target, relationship, evidence, status,
});

test("layouts message flow with fan-out, dead letters, and a consuming publisher", () => {
  const topology = {
    checked_at: "",
    nodes: [
      node("broker", "infrastructure"), node("input", "topic"),
      node("first", "subscription"), node("second", "subscription"),
      node("processor", "service"), node("output", "topic"), node("dead", "topic"),
    ],
    edges: [
      edge("broker", "input", "contains", ["observed"]),
      edge("processor", "input", "consumes"),
      edge("input", "first", "delivers_to", ["declared", "observed"]),
      edge("input", "second", "delivers_to", ["observed"]),
      edge("first", "processor", "pushes_to", ["declared", "observed"]),
      edge("processor", "output", "publishes"),
      edge("processor", "dead", "dead_letter"),
      edge("first", "dead", "dead_letter_policy", ["observed"]),
    ],
  };
  const result = layoutTopology(topology);
  const positions = Object.fromEntries(result.nodes.map(({ node, position }) => [node.id, position]));
  assert.deepEqual(result.infrastructure.map((item) => item.id), ["broker"]);
  assert.equal(result.edges.length, topology.edges.length - 3);
  assert.ok(positions.input.x < positions.first.x);
  assert.ok(positions.input.x < positions.second.x);
  assert.ok(positions.first.x < positions.processor.x);
  assert.ok(positions.processor.x < positions.output.x);
  assert.ok(positions.first.x < positions.dead.x);
  assert.deepEqual(result.hiddenDeclarations.map((item) => item.relationship).sort(), ["consumes", "dead_letter"]);
  assert.deepEqual(result.hiddenDeclarations.find((item) => item.relationship === "consumes").evidence, ["declared"]);
  const policy = result.edges.find(({ edge: item }) => item.relationship === "dead_letter_policy");
  assert.equal(policy.source, "first");
  assert.equal(policy.target, "dead");
  assert.equal(policy.description, "dead-letter policy · observed");
  for (const { points, labelPosition } of result.edges) {
    assert.ok(points.length >= 2);
    assert.ok(Number.isFinite(labelPosition.x) && Number.isFinite(labelPosition.y));
  }
  for (let i = 0; i < result.nodes.length; i++) {
    for (let j = i + 1; j < result.nodes.length; j++) {
      const a = result.nodes[i].position;
      const b = result.nodes[j].position;
      assert.ok(Math.abs(a.x - b.x) >= NODE_WIDTH || Math.abs(a.y - b.y) >= NODE_HEIGHT);
    }
  }
  assert.deepEqual(layoutTopology({ ...topology, nodes: [...topology.nodes].reverse(), edges: [...topology.edges].reverse() }), result);
});

test("preserves parallel relationships, mismatches, disconnected nodes, and cycles", () => {
  const result = layoutTopology({
    checked_at: "",
    nodes: [node("service", "service"), node("topic", "topic"), node("isolated", "subscription")],
    edges: [
      edge("service", "topic", "publishes"),
      edge("service", "topic", "consumes", ["declared"], "not_found"),
      edge("topic", "service", "pushes_to", ["observed"], "mismatch"),
    ],
  });
  assert.equal(result.nodes.length, 3);
  assert.equal(result.edges.length, 3);
  assert.match(result.edges.find(({ edge: item }) => item.status === "mismatch").label, /O · mismatch/);
  assert.match(result.edges.find(({ edge: item }) => item.status === "not_found").label, /D · not found/);
  assert.ok(result.edges.every(({ points }) => points.length >= 2));
});

test("keeps a consumption edge when only an unrelated or observed-only path exists", () => {
  const result = layoutTopology({
    checked_at: "",
    nodes: [node("service", "service"), node("topic", "topic"), node("sub", "subscription")],
    edges: [
      edge("service", "topic", "consumes"),
      edge("topic", "sub", "delivers_to", ["observed"]),
      edge("sub", "service", "pushes_to", ["observed"]),
    ],
  });
  assert.ok(result.edges.some(({ edge: item }) => item.relationship === "consumes"));
  assert.deepEqual(result.hiddenDeclarations, []);
});

test("rejects relationships referencing missing nodes", () => {
  assert.throws(() => layoutTopology({
    checked_at: "", nodes: [node("a", "topic")], edges: [edge("a", "missing", "delivers_to")],
  }), /references a missing node/);
});

test("keeps infrastructure available when there are no message-flow nodes", () => {
  const result = layoutTopology({
    checked_at: "", nodes: [node("broker", "infrastructure")], edges: [],
  });
  assert.equal(result.infrastructure.length, 1);
  assert.deepEqual(result.nodes, []);
  assert.deepEqual(result.edges, []);
});
