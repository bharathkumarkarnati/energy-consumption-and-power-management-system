# Project scope

## Objective
Develop an energy management platform for the SR University campus that organizes energy assets by block, floor and room; records consumption; analyzes usage; forecasts demand; flags unusual readings; and suggests practical energy-saving actions.

## Product 27 phases
1. Requirement analysis
2. Energy database
3. Consumption analytics
4. Dashboard development
5. API integration and automation
6. Testing and deployment

## Core data model
Block → Floor → Room → Equipment. Energy readings belong to a room and carry a source label (`simulated`, `manual` or `api`). Equipment estimates and meter readings are separate measures and must not be added together as if they were the same source.

## Initial campus assumptions
11 blocks × 3 floors × 10 rooms = 330 rooms. The first floor of each block has five labs. Each lab is represented as one desktop-equipment group with quantity 60; monitor power is included in the desktop rated wattage. Projectors are represented in classroom and lab rooms. All quantities and wattages are provisional until verified.

## Limitations / next development tasks
The current build is a functional academic prototype. Before production use, add user authentication and role permissions, CSRF protection, audit logs, validated tariff management, a meter registry and calibration metadata, robust time-series forecasting after enough actual data exists, and deployment secrets/HTTPS. Confirm campus equipment inventory and room naming with facilities staff.
