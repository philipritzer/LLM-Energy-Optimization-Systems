# LLM Energy Optimization System

This repository contains the code for my Bachelor's thesis on developing an intelligent energy management system using Large Language Models (LLMs). The project aims to optimize energy consumption in households by analyzing real-time data from a solar installation and weather forecasts.

The intelligent energy management system is designed to help users optimize their energy consumption based on real-time and historic solar energy production data and weather forecasts.

This repository showcases how both the Multi-Agent System and Single-Agent System were implemented. Please note that this repository is intended to demonstrate the code and system architecture; however, the actual endpoints to retrieve data are not made public due to the private nature of the data involved.

## Overview

- `chat_apps/`: Contains both Streamlit applications for user interaction.
- `cloud_functions/`: Contains the endpoints made available via Google Cloud Functions.
- `raspberry_pi_scripts/`: Contains the scripts that run on the Raspberry Pi.
- `multi_agent_system.py`: Contains the raw Multi-Agent System without a user interface 
- `single_agent_system.py`: Contains the raw Single-Agent System without a user interface 