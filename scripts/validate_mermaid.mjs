import { JSDOM } from "jsdom";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  pretendToBeVisual: true,
  url: "https://example.com/",
});
for (const key of [
  "window", "document", "navigator", "DOMParser", "HTMLElement",
  "SVGElement", "Element", "Node", "MutationObserver", "getComputedStyle",
]) {
  const value = key === "window" ? dom.window : dom.window[key];
  try {
    Object.defineProperty(globalThis, key, { value, configurable: true, writable: true });
  } catch {
    // 某些全局属性只读（如 Node 22 的 navigator），跳过即可
  }
}
try {
  Object.defineProperty(globalThis, "self", { value: dom.window, configurable: true });
} catch {}

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => (input += chunk));
process.stdin.on("end", async () => {
  let data;
  try {
    data = JSON.parse(input);
  } catch {
    console.error("bad json input");
    process.exit(2);
  }
  const { default: mermaid } = await import("mermaid");
  mermaid.initialize({ startOnLoad: false });
  const results = [];
  for (const diagram of data.diagrams || []) {
    try {
      await mermaid.parse(diagram);
      results.push(true);
    } catch {
      results.push(false);
    }
  }
  process.stdout.write(JSON.stringify({ results }) + "\n");
});
