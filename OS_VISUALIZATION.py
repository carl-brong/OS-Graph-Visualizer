#Carl Brong
#OS Visualization Script

import os
import json
import datetime
import stat
import platform
from pathlib import Path
import pandas as pd
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from tqdm import tqdm
import scipy  
import colorsys
import networkx as nx
import matplotlib.pyplot as plt



def get_file_metadata(filepath):
    if not os.access(filepath, os.R_OK):
        print(f"No read access to: {filepath}")
        return None
        
    try:
        stats = os.stat(filepath)
    except (OSError, PermissionError) as e:
        print(f"Error accessing {filepath}: {str(e)}")
        return None
        
    try:
        metadata = {
            'path': str(filepath),
            'filename': os.path.basename(filepath),
            'directory': os.path.dirname(filepath),
            'size_bytes': stats.st_size,
            'creation_time': datetime.datetime.fromtimestamp(stats.st_ctime).isoformat(),
            'file_extension': os.path.splitext(filepath)[1].lower(),
            'is_system_file': is_system_file(filepath),
        }
        return metadata
    except Exception as e:
        print(f"Error processing {filepath}: {str(e)}")
        return None


#for Windows
def is_system_file(filepath):
    system_paths = [
        '/System/', '/Windows/', '/Program Files/', '/Program Files (x86)/',
        '/Library/', '/bin/', '/etc/', '/var/', '/usr/'
    ]
    return any(sys_path in str(filepath) for sys_path in system_paths)


def handle_walk_error(error):
        print(f"Error accessing directory: {error}")


def collect_filesystem_metadata(start_path, exclude_dirs=None):
    if exclude_dirs is None:
        exclude_dirs = ['.git', 'node_modules', '__pycache__', 'temp']
    
    if not os.path.exists(start_path):
        raise FileNotFoundError(f"Start path does not exist: {start_path}")
    
    all_metadata = []
    total_size = 0
    
    #count total files for progress bar
    print("Counting files in OS...")
    total_files = sum([len(files) for _, _, files in os.walk(start_path)])
    print(f"Found {total_files} files to process")
    
    
    
    #progress bar for file processing
    pbar = tqdm(total=total_files, desc="Processing files", unit="files")
    
    for root, dirs, files in os.walk(start_path, topdown=True, onerror=handle_walk_error):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        accessible_dirs = []
        for d in dirs:
            full_path = os.path.join(root, d)
            try:
                if os.access(full_path, os.R_OK):
                    accessible_dirs.append(d)
                else:
                    print(f"No permission to access directory: {full_path}")
            except OSError as e:
                print(f"Error checking directory access {full_path}: {e}")
        
        dirs[:] = accessible_dirs
        
        for file in files:
            filepath = os.path.join(root, file)
            metadata = get_file_metadata(filepath)
            if metadata:
                all_metadata.append(metadata)
                total_size += metadata['size_bytes']
            pbar.update(1)
    
    pbar.close()
    return all_metadata, total_size


def size_to_color(size_ratio):
        #convert size to hue 
        hue = (size_ratio * 0.8 + 0.7) % 1.0
        return colorsys.hsv_to_rgb(hue, 1.0, 1.0)


def create_directory_graph(metadata_df):
       
    print("Creating visualization...")   
    G = nx.Graph()
    
    #process each file path to create nodes and edges
    print("Building graph structure...")
    with tqdm(total=len(metadata_df), desc="Adding nodes") as pbar:
        for _, row in metadata_df.iterrows():
            path_parts = Path(row['path']).parts
            
            #add nodes and edges
            for i in range(len(path_parts)):
                current = os.path.join(*path_parts[:i+1])
                G.add_node(current, size=row['size_bytes'] if i == len(path_parts)-1 else 0)
                
                if i > 0:
                    parent = os.path.join(*path_parts[:i])
                    G.add_edge(parent, current)
            pbar.update(1)

    #color based on file sizes
    print("Calculating node colors...")
    colors = []
    max_size = max(nx.get_node_attributes(G, 'size').values())
    
    with tqdm(total=len(G.nodes()), desc="Processing nodes") as pbar:
        for node in G.nodes():
            size = G.nodes[node]['size']
            if size > 0:  
                size_ratio = size / max_size
            else: 
                dir_size = sum(G.nodes[n]['size'] for n in nx.descendants(G, node))
                size_ratio = dir_size / max_size
            colors.append(size_to_color(size_ratio))
            pbar.update(1)

    print("Generating visualization...")
    plt.figure(figsize=(40, 40), facecolor='black', dpi=1300)
    ax = plt.gca()
    ax.set_facecolor('black')
    
    #create layout with more iterations for better arrangement
    print("Calculating layout...")
    pos = nx.spring_layout(G, k=1/np.sqrt(len(G.nodes())), iterations=25)
    
    #draw the network with uniform node size
    nx.draw(G, pos,
           node_size=1,  
           node_color=colors,
           edge_color='#303030',
           alpha=0.9,
           with_labels=False,
           width=0.1)
    
    plt.axis('off')
    return plt.gcf()

def save_metadata_and_visualizations(metadata, output_dir):
    try:
        os.makedirs(output_dir, exist_ok=True)
        print(f"\nSaving files to: {output_dir}")
        
        df = pd.DataFrame(metadata)
        if df.empty:
            print("No data to visualize.")
            return
            
        print(f"Processing {len(df)} files for visualization...")
        
        try:
            fig = create_directory_graph(df)
            fig_path = os.path.join(output_dir, 'filesystem_structure.png')
            fig.savefig(fig_path, facecolor='black', bbox_inches='tight', dpi=300)
            plt.close(fig)
            print(f"Visualization saved to: {fig_path}")
        except Exception as e:
            print(f"Error creating visualization: {str(e)}")
        
        csv_path = os.path.join(output_dir, 'filesystem_metadata.csv')
        df.to_csv(csv_path, index=False)
        print(f"CSV saved to: {csv_path}")
        
        summary = {
            'total_files': int(len(metadata)),
            'total_size_bytes': int(df['size_bytes'].sum()),
            'file_types': {k: int(v) for k, v in df['file_extension'].value_counts().to_dict().items()},
            'system_files_count': int(sum(1 for item in metadata if item['is_system_file'])),
            'user_files_count': int(sum(1 for item in metadata if not item['is_system_file'])),
            'scan_time': datetime.datetime.now().isoformat(),
            'system_info': {
                'platform': platform.system(),
                'platform_release': platform.release(),
                'machine': platform.machine()
            }
        }
        
        summary_path = os.path.join(output_dir, 'summary.json')
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
            
    except Exception as e:
        print(f"Error saving data: {str(e)}")
        raise

def main():
    #change as needed
    start_path = "/home/research"  #start directory (change as needed)
    output_dir = "/home/research/Desktop/OS_Visualization" #where to save the output (change as needed)
    exclude_dirs = ['.git', 'node_modules', '__pycache__', 'temp', 'Downloads']
    
    print(f"Starting metadata collection from {start_path}")
    metadata, total_size = collect_filesystem_metadata(start_path, exclude_dirs)
    print(f"Collected metadata for {len(metadata)} files")
    print(f"Total size scanned: {total_size / (1024**3):.2f} GB")
    
    save_metadata_and_visualizations(metadata, output_dir)
    print(f"Metadata and visualizations saved to {output_dir}")
    #print(f"Open {output_dir}/filesystem_visualization.html in a web browser to view the interactive visualization")

if __name__ == "__main__":
    main()
