# GeoScheduler: Spatio-Temporal Traffic Prioritization Using GIS

GeoScheduler is a spatial informatics project that models urban commuter flow and dynamically prioritizes traffic junctions based on real movement patterns rather than fixed signal timings. Inspired by fair scheduling principles from operating systems, the system identifies dominant commuter corridors and assigns adaptive priority weights to intersections during peak and off-peak periods.

The project is implemented as custom QGIS plugins and demonstrated on the Hyderabad road network.

---

## Problem Motivation

Most urban traffic signals operate on static timing cycles that fail to adapt to changing commuter patterns. In cities with strong directional flows—such as residential-to-work travel during morning peaks—this leads to inefficient signal allocation and unnecessary congestion.

GeoScheduler addresses this by answering a simple question:

> Which roads and junctions are actually used the most by commuters, and how should signal priority change over time?

---

## Core Idea

The system treats **traffic flow like a scheduling problem**:

- Roads and junctions are treated as shared resources  
- Commuter routes act like competing processes  
- Priority is dynamically assigned based on actual usage patterns  

During peak hours, dominant commuter corridors receive higher priority, while cross-traffic is deprioritized. During off-peak hours, priority is distributed evenly to ensure fairness.

---

## Data Sources

The model integrates multiple spatial datasets:

- **OpenStreetMap (OSM)** – Road network and junction topology  
- **Land Use / Land Cover (LULC)** – Residential and commercial zones  
- **Population Density (WorldPop)** – Identifying residential origins  
- **Points of Interest (OSM POIs)** – Offices, tech parks, commercial hubs  

---

## Methodology

### 1. Origin–Destination Identification
- Residential zones combined with population density define **origins**
- Commercial areas and office POIs define **destinations**
- Polygons are manually refined within the Area of Interest (AOI)

### 2. Route Generation
- Multiple origin–destination point pairs are sampled
- Shortest paths are generated using QGIS network analysis (QNEAT3)
- Each path represents a potential commuter trajectory

### 3. Corridor Extraction
- All routes are spatially overlaid
- Roads used by many routes are classified as **primary corridors**
- Roads with low usage are treated as secondary or irrelevant

### 4. Junction Prioritization
- Junctions touched by multiple high-frequency routes are marked critical
- Each junction is assigned directional weights:
  - Higher weight → main commuter flow
  - Lower weight → cross traffic

---

## Scheduler Analogy

GeoScheduler is inspired by the **Completely Fair Scheduler (CFS)** used in Linux:

| Operating Systems | Traffic System |
|------------------|----------------|
| Processes        | Commuter routes |
| CPU time         | Signal green time |
| Scheduling weight| Junction priority |
| Fair scheduling  | Off-peak equal priority |

This abstraction allows traffic signals to adapt based on demand rather than rigid timing rules.

---

## QGIS Plugins

The project includes **two custom PyQGIS plugins**:

### 1. GeoScheduler (Core Plugin)
- Computes commuter routes from origin to destination zones
- Identifies dominant corridors and high-priority junctions
- Assigns dynamic priority weights to junction attributes

### 2. GeoScheduler Visualizer
- Toggles between **AM Peak** and **Off-Peak** modes
- Automatically updates junction weights
- Provides real-time visualization of priority changes inside QGIS

---

## Modes of Operation

### AM Peak Mode
- Boosts priority along dominant home → work corridors
- Reduces weight for cross traffic
- Optimized for directional commuter flow

### Off-Peak Mode
- Equal priority assigned across all directions
- Mimics fair, balanced signal operation
- Prevents starvation of low-traffic routes

---

## Key Features

- Data-driven traffic prioritization (no hard-coded directions)
- GIS-based network analysis
- Scheduler-inspired dynamic weighting
- Modular QGIS plugin architecture
- Scalable to larger urban areas

---

## Results & Demonstration

- Successfully identified main commuter corridors in Hyderabad
- Junction weights changed meaningfully between peak and off-peak
- Demonstrated how spatial analytics can inform traffic control logic

---

## Future Extensions

- Integration with real-time traffic APIs
- Traffic simulation and validation
- City-wide scaling
- Adaptive learning of commuter patterns over time

---

## License

This project is intended for academic and research use.
