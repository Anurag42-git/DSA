import sys
import threading
import tkinter as tk
from tkinter import simpledialog, messagebox
from typing import Dict, List, Tuple, Optional, Set
import heapq


VertexId = int
Edge = Tuple[VertexId, VertexId, float]


class DisjointSet:
	def __init__(self, n: int) -> None:
		self.parent = list(range(n))
		self.rank = [0] * n

	def find(self, x: int) -> int:
		if self.parent[x] != x:
			self.parent[x] = self.find(self.parent[x])
		return self.parent[x]

	def union(self, x: int, y: int) -> bool:
		rx = self.find(x)
		ry = self.find(y)
		if rx == ry:
			return False
		if self.rank[rx] < self.rank[ry]:
			self.parent[rx] = ry
		elif self.rank[rx] > self.rank[ry]:
			self.parent[ry] = rx
		else:
			self.parent[ry] = rx
			self.rank[rx] += 1
		return True


class MSTVisualizer:
	RADIUS = 16
	COLOR_BG = "#111927"
	COLOR_CANVAS = "#0b1220"
	COLOR_NODE = "#f59e0b"  # amber for visited nodes in Prim
	COLOR_NODE_IDLE = "#94a3b8"
	COLOR_EDGE = "#64748b"
	COLOR_EDGE_CURRENT = "#3b82f6"  # blue
	COLOR_EDGE_REJECT = "#ef4444"  # red
	COLOR_EDGE_MST = "#10b981"  # green
	COLOR_TEXT = "#e5e7eb"

	def __init__(self, root: tk.Tk, total_vertices: int) -> None:
		self.root = root
		self.total_vertices = total_vertices
		self.root.title("MST Visualizer: Kruskal then Prim")
		self.root.configure(bg=self.COLOR_BG)

		self.canvas = tk.Canvas(self.root, width=900, height=600, bg=self.COLOR_CANVAS, highlightthickness=0)
		self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

		self.sidebar = tk.Frame(self.root, bg=self.COLOR_BG)
		self.sidebar.pack(side=tk.RIGHT, fill=tk.Y)

		self.instructions = tk.Label(
			self.sidebar,
			text=(
				"Steps:\n"
				f"1) Click to place exactly {self.total_vertices} vertices.\n"
				"2) Create edges: click two vertices, enter weight.\n"
				"3) Press 'Run Visualizations'.\n\n"
				"Colors:\n- Green: in final MST\n- Blue: currently considered edge\n- Red: rejected edge\n- Amber: visited nodes (Prim)"
			),
			fg=self.COLOR_TEXT,
			bg=self.COLOR_BG,
			justify=tk.LEFT,
			anchor="w",
			padx=12,
			pady=12,
			wraplength=320,
		)
		self.instructions.pack(anchor="n")

		self.btn_run = tk.Button(self.sidebar, text="Run Visualizations (Kruskal → Prim)", command=self.run_visualizations)
		self.btn_run.pack(pady=8, padx=12, fill=tk.X)

		self.btn_reset_colors = tk.Button(self.sidebar, text="Reset Colors", command=self.reset_colors)
		self.btn_reset_colors.pack(pady=8, padx=12, fill=tk.X)

		self.status_var = tk.StringVar(value="Place vertices by clicking on canvas")
		self.status = tk.Label(self.sidebar, textvariable=self.status_var, fg=self.COLOR_TEXT, bg=self.COLOR_BG, anchor="w", padx=12)
		self.status.pack(fill=tk.X, pady=12)

		self.vertex_positions: Dict[VertexId, Tuple[float, float]] = {}
		self.vertex_items: Dict[VertexId, Tuple[int, int]] = {}  # oval_id, text_id
		self.edges: List[Edge] = []
		self.edge_items: Dict[Tuple[VertexId, VertexId], Tuple[int, int]] = {}  # line_id, text_id
		self.vertex_click_buffer: List[VertexId] = []

		self.placing_vertices_remaining = self.total_vertices
		self.is_animating = False
		self.prim_start: Optional[VertexId] = None
		self.kruskal_total_weight: Optional[float] = None
		self.prim_total_weight: Optional[float] = None

		self.canvas.bind("<Button-1>", self.on_canvas_click)

	def on_canvas_click(self, event: tk.Event) -> None:
		if self.is_animating:
			return
		if self.placing_vertices_remaining > 0:
			vid = len(self.vertex_positions)
			self.add_vertex(vid, event.x, event.y)
			self.placing_vertices_remaining -= 1
			if self.placing_vertices_remaining == 0:
				self.status_var.set("Vertices placed. Create edges by selecting two vertices.")
			else:
				self.status_var.set(f"Place {self.placing_vertices_remaining} more vertices.")
			return

		# Select vertices for edge creation
		clicked_vid = self.find_vertex_at(event.x, event.y)
		if clicked_vid is None:
			return
		self.vertex_click_buffer.append(clicked_vid)
		if len(self.vertex_click_buffer) == 2:
			u, v = self.vertex_click_buffer
			self.vertex_click_buffer.clear()
			if u == v:
				return
			# Normalize edge key
			key = (min(u, v), max(u, v))
			if key in self.edge_items:
				messagebox.showinfo("Edge exists", "Edge already exists between selected vertices.")
				return
			w = self.prompt_weight(u, v)
			if w is None:
				return
			self.add_edge(u, v, w)
			self.status_var.set(f"Added edge ({u}, {v}, {w}). Add more or run visualization.")

	def add_vertex(self, vid: VertexId, x: float, y: float) -> None:
		oval = self.canvas.create_oval(
			x - self.RADIUS,
			y - self.RADIUS,
			x + self.RADIUS,
			y + self.RADIUS,
			fill=self.COLOR_NODE_IDLE,
			outline="#1f2937",
			width=2,
		)
		label = self.canvas.create_text(x, y, text=str(vid), fill=self.COLOR_TEXT, font=("Segoe UI", 10, "bold"))
		self.vertex_positions[vid] = (x, y)
		self.vertex_items[vid] = (oval, label)

	def prompt_weight(self, u: VertexId, v: VertexId) -> Optional[float]:
		try:
			w_str = simpledialog.askstring("Edge weight", f"Enter weight for edge ({u}, {v}):", parent=self.root)
			if w_str is None:
				return None
			w = float(w_str)
			if w < 0:
				messagebox.showerror("Invalid weight", "Weight must be non-negative.")
				return None
			return w
		except ValueError:
			messagebox.showerror("Invalid input", "Please enter a numeric weight.")
			return None

	def add_edge(self, u: VertexId, v: VertexId, w: float) -> None:
		x1, y1 = self.vertex_positions[u]
		x2, y2 = self.vertex_positions[v]
		line = self.canvas.create_line(x1, y1, x2, y2, fill=self.COLOR_EDGE, width=3)
		mx, my = (x1 + x2) / 2, (y1 + y2) / 2
		text = self.canvas.create_text(mx, my - 10, text=str(w), fill=self.COLOR_TEXT, font=("Segoe UI", 9))
		self.edges.append((u, v, w))
		key = (min(u, v), max(u, v))
		self.edge_items[key] = (line, text)

	def find_vertex_at(self, x: float, y: float) -> Optional[VertexId]:
		for vid, (vx, vy) in self.vertex_positions.items():
			if (vx - x) ** 2 + (vy - y) ** 2 <= self.RADIUS ** 2:
				return vid
		return None

	def reset_colors(self) -> None:
		for key, (line, _) in self.edge_items.items():
			self.canvas.itemconfig(line, fill=self.COLOR_EDGE)
		for vid, (oval, _) in self.vertex_items.items():
			self.canvas.itemconfig(oval, fill=self.COLOR_NODE_IDLE)
		self.status_var.set("Colors reset. Ready.")

	def run_visualizations(self) -> None:
		if self.is_animating:
			return
		if len(self.vertex_positions) != self.total_vertices:
			messagebox.showwarning("Vertices incomplete", f"Place exactly {self.total_vertices} vertices first.")
			return
		if len(self.edges) == 0:
			messagebox.showwarning("No edges", "Add at least one edge.")
			return
		self.is_animating = True
		self.status_var.set("Running Kruskal visualization...")
		self.reset_colors()
		self.animate_kruskal(on_complete=self.run_prim_after_kruskal)

	def run_prim_after_kruskal(self) -> None:
		# Show Kruskal total weight if computed
		if self.kruskal_total_weight is not None:
			self.status_var.set(f"Kruskal done. Total weight = {self.kruskal_total_weight}. Running Prim visualization...")
		else:
			self.status_var.set("Kruskal done. Running Prim visualization...")
		# Reset edge colors, keep MST from Kruskal not highlighted
		for key, (line, _) in self.edge_items.items():
			self.canvas.itemconfig(line, fill=self.COLOR_EDGE)
		for vid, (oval, _) in self.vertex_items.items():
			self.canvas.itemconfig(oval, fill=self.COLOR_NODE_IDLE)
		self.animate_prim(on_complete=self.finish_animation)

	def finish_animation(self) -> None:
		self.is_animating = False
		if self.kruskal_total_weight is not None and self.prim_total_weight is not None:
			self.status_var.set(f"Completed: Kruskal then Prim. Totals — Kruskal: {self.kruskal_total_weight}, Prim: {self.prim_total_weight}")
		elif self.kruskal_total_weight is not None:
			self.status_var.set(f"Completed: Kruskal then Prim. Kruskal total = {self.kruskal_total_weight}")
		elif self.prim_total_weight is not None:
			self.status_var.set(f"Completed: Kruskal then Prim. Prim total = {self.prim_total_weight}")
		else:
			self.status_var.set("Completed: Kruskal then Prim.")

	def animate_kruskal(self, on_complete) -> None:
		n = self.total_vertices
		dsu = DisjointSet(n)
		sorted_edges = sorted(self.edges, key=lambda e: e[2])
		mst_edges: List[Edge] = []

		steps: List[Tuple[str, Tuple[VertexId, VertexId, float]]] = []
		for (u, v, w) in sorted_edges:
			steps.append(("consider", (u, v, w)))
			if dsu.union(u, v):
				mst_edges.append((u, v, w))
				steps.append(("accept", (u, v, w)))
			else:
				steps.append(("reject", (u, v, w)))

		current_total: float = 0.0
		def do_step(i: int) -> None:
			if i >= len(steps):
				# Finalize MST edges as green
				for (u, v, w) in mst_edges:
					key = (min(u, v), max(u, v))
					line, _ = self.edge_items[key]
					self.canvas.itemconfig(line, fill=self.COLOR_EDGE_MST)
				# Compute and show total weight for Kruskal
				total = sum(w for (_, _, w) in mst_edges)
				self.kruskal_total_weight = total
				self.status_var.set(f"Kruskal completed. Total weight (green) = {total}")
				self.root.after(800, on_complete)
				return
			action, (u, v, w) = steps[i]
			key = (min(u, v), max(u, v))
			line, _ = self.edge_items[key]
			if action == "consider":
				self.canvas.itemconfig(line, fill=self.COLOR_EDGE_CURRENT)
				self.status_var.set(f"Kruskal: considering edge ({u},{v}) w={w}")
				self.root.after(700, lambda: do_step(i + 1))
			elif action == "accept":
				self.canvas.itemconfig(line, fill=self.COLOR_EDGE_MST)
				current_total += w
				self.status_var.set(f"Kruskal: accepted edge ({u},{v}) | MST total (green) = {current_total}")
				self.root.after(700, lambda: do_step(i + 1))
			else:  # reject
				self.canvas.itemconfig(line, fill=self.COLOR_EDGE_REJECT)
				self.status_var.set(f"Kruskal: rejected edge ({u},{v})")
				self.root.after(700, lambda: do_step(i + 1))

		do_step(0)

	def animate_prim(self, on_complete) -> None:
		start = self.prompt_start_vertex_cli()
		if start is None or start not in self.vertex_positions:
			messagebox.showerror("Invalid start", "Starting vertex is invalid. Aborting Prim.")
			on_complete()
			return
		self.prim_start = start

		n = self.total_vertices
		adj: Dict[int, List[Tuple[float, int, int]]] = {i: [] for i in range(n)}
		for (u, v, w) in self.edges:
			adj[u].append((w, u, v))
			adj[v].append((w, v, u))

		visited: Set[int] = set()
		heap: List[Tuple[float, int, int]] = []

		def push_edges(u: int) -> None:
			for (w, _, v) in adj[u]:
				if v not in visited:
					heapq.heappush(heap, (w, u, v))

		order: List[Tuple[str, Tuple]] = []
		total_weight: float = 0.0
		# Start from start vertex
		order.append(("visit", (start,)))
		visited.add(start)
		push_edges(start)
		while heap and len(visited) < n:
			w, u, v = heapq.heappop(heap)
			order.append(("consider", (u, v, w)))
			if v in visited:
				order.append(("skip", (u, v, w)))
				continue
			order.append(("accept", (u, v, w)))
			total_weight += w
			visited.add(v)
			order.append(("visit", (v,)))
			push_edges(v)

		# Reset for animation playthrough
		for vid, (oval, _) in self.vertex_items.items():
			self.canvas.itemconfig(oval, fill=self.COLOR_NODE_IDLE)
		for key, (line, _) in self.edge_items.items():
			self.canvas.itemconfig(line, fill=self.COLOR_EDGE)

		def do_step(i: int) -> None:
			if i >= len(order):
				# Record and show total weight for Prim
				self.prim_total_weight = total_weight
				self.status_var.set(f"Prim completed. Total weight (green) = {total_weight}")
				self.root.after(800, on_complete)
				return
			action, data = order[i]
			if action == "visit":
				(u,) = data
				oval, _ = self.vertex_items[u]
				self.canvas.itemconfig(oval, fill=self.COLOR_NODE)
				self.status_var.set(f"Prim: visited {u}")
				self.root.after(600, lambda: do_step(i + 1))
			elif action == "consider":
				u, v, w = data
				key = (min(u, v), max(u, v))
				line, _ = self.edge_items[key]
				self.canvas.itemconfig(line, fill=self.COLOR_EDGE_CURRENT)
				self.status_var.set(f"Prim: considering ({u},{v}) w={w}")
				self.root.after(700, lambda: do_step(i + 1))
			elif action == "skip":
				u, v, w = data
				key = (min(u, v), max(u, v))
				line, _ = self.edge_items[key]
				self.canvas.itemconfig(line, fill=self.COLOR_EDGE_REJECT)
				self.status_var.set(f"Prim: rejected ({u},{v}) (forms cycle)")
				self.root.after(700, lambda: do_step(i + 1))
			elif action == "accept":
				u, v, w = data
				key = (min(u, v), max(u, v))
				line, _ = self.edge_items[key]
				self.canvas.itemconfig(line, fill=self.COLOR_EDGE_MST)
				total_weight += w
				self.status_var.set(f"Prim: accepted ({u},{v}) | MST total (green) = {total_weight}")
				self.root.after(700, lambda: do_step(i + 1))

		do_step(0)

	def prompt_start_vertex_cli(self) -> Optional[int]:
		# Prompt in a blocking manner in a separate modal dialog informing user to check console
		def ask_input() -> Optional[int]:
			print("Enter starting vertex for Prim (0..{}): ".format(self.total_vertices - 1))
			try:
				value = sys.stdin.readline()
				if not value:
					return None
				v = int(value.strip())
				if 0 <= v < self.total_vertices:
					return v
				return None
			except Exception:
				return None

		# Temporarily disable GUI interactions and show info
		messagebox.showinfo(
			"Select starting vertex",
			"Please focus the console/terminal and enter a starting vertex index (0-based).",
		)
		# Read synchronously (Tk mainloop still runs; stdin is blocking application's flow which is acceptable here by design)
		return ask_input()


def main() -> None:
	# CLI prompt for total vertices before GUI starts
	print("Enter total number of vertices (positive integer): ")
	n: Optional[int] = None
	try:
		line = sys.stdin.readline()
		n = int(line.strip())
		if n <= 0:
			raise ValueError
	except Exception:
		print("Invalid input. Exiting.")
		return

	root = tk.Tk()
	app = MSTVisualizer(root, n)
	root.mainloop()


if __name__ == "__main__":
	main()


