import networkx as nx
import matplotlib.pyplot as plt
import heapq

# --- Disjoint Set Union (DSU) Data Structure for Kruskal's ---
# A helper class to efficiently track connected components of the graph.
class DSU:
    def __init__(self, nodes):
        # Initialize each node as its own parent (a set of one).
        self.parent = {node: node for node in nodes}

    def find(self, i):
        # Find the representative (root) of the set containing element i.
        # Uses path compression for optimization.
        if self.parent[i] == i:
            return i
        self.parent[i] = self.find(self.parent[i])
        return self.parent[i]

    def union(self, x, y):
        # Merge the sets containing x and y.
        root_x = self.find(x)
        root_y = self.find(y)
        if root_x != root_y:
            self.parent[root_x] = root_y
            return True # Return True if a merge happened
        return False # Return False if they were already in the same set

# --- Algorithm Implementations (as Generators) ---

def kruskal_generator(G):
    """
    Yields the state of the graph at each step of Kruskal's algorithm.
    """
    # Create a list of all edges, sorted by weight
    edges = sorted(G.edges(data=True), key=lambda t: t[2].get('weight', 1))
    dsu = DSU(G.nodes())
    mst_edges = []
    
    yield {'step': 'Initial Graph', 'mst_edges': [], 'considered_edge': None, 'status': ''}

    for u, v, data in edges:
        weight = data.get('weight', 1)
        # Check if the edge connects two different components
        status = 'Checking edge ({}, {}) with weight {}'.format(u, v, weight)
        yield {'step': status, 'mst_edges': list(mst_edges), 'considered_edge': (u, v), 'status': 'considering'}
        
        if dsu.union(u, v):
            mst_edges.append((u, v))
            status = 'Added edge ({}, {})'.format(u, v)
            yield {'step': status, 'mst_edges': list(mst_edges), 'considered_edge': (u, v), 'status': 'added'}
        else:
            status = 'Rejected edge ({}, {}) - creates a cycle'.format(u, v)
            yield {'step': status, 'mst_edges': list(mst_edges), 'considered_edge': (u, v), 'status': 'rejected'}

    total_weight = sum(G[u][v]['weight'] for u, v in mst_edges)
    yield {'step': f'Final MST Found! Total Weight: {total_weight}', 'mst_edges': mst_edges, 'considered_edge': None, 'status': 'done'}

def prim_generator(G, start_node):
    """
    Yields the state of the graph at each step of Prim's algorithm.
    """
    visited = {start_node}
    mst_edges = []
    # Priority queue stores (weight, node1, node2)
    edges_heap = []

    # Initialize heap with edges from the start node
    for neighbor in G.neighbors(start_node):
        weight = G[start_node][neighbor]['weight']
        heapq.heappush(edges_heap, (weight, start_node, neighbor))
    
    yield {
        'step': f'Start with node {start_node}', 
        'mst_edges': [], 
        'visited': set(visited),
        'heap': list(edges_heap),
        'considered_edge': None,
        'status': 'initial'
    }

    while edges_heap and len(visited) < len(G.nodes()):
        weight, u, v = heapq.heappop(edges_heap)

        status = f"Considering edge ({u}, {v}) with weight {weight} from priority queue"
        yield {
            'step': status,
            'mst_edges': list(mst_edges),
            'visited': set(visited),
            'heap': list(edges_heap),
            'considered_edge': (u, v),
            'status': 'considering'
        }

        if v not in visited:
            visited.add(v)
            mst_edges.append((u, v))
            status = f"Added node {v} and edge ({u}, {v})"
            
            # Add new edges from the newly visited node to the heap
            for neighbor in G.neighbors(v):
                if neighbor not in visited:
                    new_weight = G[v][neighbor]['weight']
                    heapq.heappush(edges_heap, (new_weight, v, neighbor))
            
            yield {
                'step': status,
                'mst_edges': list(mst_edges),
                'visited': set(visited),
                'heap': list(edges_heap),
                'considered_edge': (u, v),
                'status': 'added'
            }

    total_weight = sum(G[u][v]['weight'] for u, v in mst_edges)
    yield {
        'step': f'Final MST Found! Total Weight: {total_weight}', 
        'mst_edges': mst_edges, 
        'visited': visited,
        'heap': [],
        'considered_edge': None,
        'status': 'done'
    }

# --- Visualization Function ---

def visualize_algorithm(G, algorithm_generator, title):
    """
    Generic visualization function that takes a graph and an algorithm generator.
    """
    pos = nx.spring_layout(G, seed=42)  # Seed for reproducible layouts
    edge_labels = nx.get_edge_attributes(G, 'weight')

    # Create the plot
    fig, ax = plt.subplots(figsize=(10, 8))
    fig.canvas.manager.set_window_title(title)
    
    # Define colors
    default_node_color = '#a3a3a3'
    visited_node_color = '#f59e0b' # Amber
    default_edge_color = '#d4d4d4'
    mst_edge_color = '#10b981' # Emerald
    considering_edge_color = '#3b82f6' # Blue
    rejected_edge_color = '#ef4444' # Red

    for state in algorithm_generator:
        ax.clear()
        
        # --- Draw Nodes ---
        if 'visited' in state: # Prim's specific
            node_colors = [visited_node_color if n in state['visited'] else default_node_color for n in G.nodes()]
            nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, node_size=700)
        else: # Kruskal's
            nx.draw_networkx_nodes(G, pos, ax=ax, node_color=default_node_color, node_size=700)

        # --- Draw Edges ---
        # Draw all edges in default color first
        nx.draw_networkx_edges(G, pos, ax=ax, edge_color=default_edge_color, width=1.5)

        # Draw MST edges
        if state['mst_edges']:
            nx.draw_networkx_edges(G, pos, ax=ax, edgelist=state['mst_edges'], edge_color=mst_edge_color, width=3.0)

        # Highlight the considered/rejected edge
        if state['considered_edge']:
            u, v = state['considered_edge']
            color = considering_edge_color
            if state['status'] == 'added':
                color = mst_edge_color
            elif state['status'] == 'rejected':
                color = rejected_edge_color
                
            nx.draw_networkx_edges(G, pos, ax=ax, edgelist=[(u,v)], edge_color=color, width=3.5, style='dashed')
        
        # --- Draw Labels ---
        nx.draw_networkx_labels(G, pos, ax=ax, font_size=12, font_color='white', font_weight='bold')
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, ax=ax, font_color='black')
        
        # --- Set Title and Display ---
        ax.set_title(state['step'], fontsize=14)
        plt.tight_layout()
        plt.pause(1.5) # Pause to create animation effect

    plt.show()

# --- Main Execution ---
if __name__ == "__main__":
    # Define a sample graph
    G = nx.Graph()
    nodes = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
    edges_with_weights = [
        ('A', 'B', 7), ('A', 'D', 5),
        ('B', 'C', 8), ('B', 'D', 9), ('B', 'E', 7),
        ('C', 'E', 5),
        ('D', 'E', 15), ('D', 'F', 6),
        ('E', 'F', 8), ('E', 'G', 9),
        ('F', 'G', 11)
    ]
    G.add_nodes_from(nodes)
    for u, v, w in edges_with_weights:
        G.add_edge(u, v, weight=w)

    # Visualize Kruskal's Algorithm
    print("--- Starting Kruskal's Algorithm Visualization ---")
    kruskal_gen = kruskal_generator(G)
    visualize_algorithm(G, kruskal_gen, "Kruskal's Algorithm Visualization")
    print("--- Kruskal's Visualization Complete ---")

    # Visualize Prim's Algorithm
    print("\n--- Starting Prim's Algorithm Visualization ---")
    start_node = 'A'
    prim_gen = prim_generator(G, start_node=start_node)
    visualize_algorithm(G, prim_gen, f"Prim's Algorithm Visualization (Starting from Node {start_node})")
    print("--- Prim's Visualization Complete ---")
