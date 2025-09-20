## MST Visualizer (Kruskal then Prim)

An interactive Tkinter tool for building a graph and visualizing Minimum Spanning Tree algorithms.

### Features
- Click to place vertices (you choose the total count in the console before the GUI launches)
- Click two vertices to create an undirected edge and enter its weight
- Color scheme:
  - Green: edges in the final MST
  - Blue: edge currently being considered
  - Red: rejected edge
  - Amber: visited nodes (Prim)
- Runs Kruskal first, then Prim
- Prompts in the console for a valid starting vertex for Prim

### Requirements
- Python 3.9+

### Run
```bash
python mst_visualizer.py
```

Follow the console prompt to enter the total number of vertices. In the GUI:
1. Click to place exactly N vertices.
2. Click two vertices to add an edge and enter a numeric non-negative weight.
3. Click "Run Visualizations (Kruskal → Prim)".
4. When prompted, enter the starting vertex for Prim in the console (0-based index).

### Notes
- Self-loops are ignored. Duplicate edges are prevented.
- The graph is undirected and weights must be non-negative.

