# Queuing Theory Dashboard Foundation

## Project Overview
The Queuing Theory Dashboard Foundation is a comprehensive tool designed to analyze and visualize queuing systems through various queuing theory models.

## Features
- **Real-time Analytics**: Monitor queue lengths, wait times, and service times live.
- **Model Types**: Supports M/M/1, M/M/c, M/G/1, and other queuing models.
- **User-Friendly Interface**: Easy navigation with clear visualizations.
- **Export Options**: Download reports and data visualizations in multiple formats.

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/akselsjunjun-maker/QUEUING_THEORY_NOVAMART.git
   cd QUEUING_THEORY_NOVAMART
   ```
2. Install the required dependencies:
   ```bash
   npm install
   ```
3. Run the application:
   ```bash
   npm start
   ```

## Usage
- Access the dashboard via your web browser at `http://localhost:3000`.
- Input your queue parameters and select the model type for analysis.

## Input Format
Input the following parameters according to the selected model:
- Arrival rate (λ)
- Service rate (μ)
- Number of servers (c) (if applicable)

## Metrics
- Average queue length
- Average wait time in the queue
- Average time in the system
- Server utilization

## Stability Conditions
- For M/M/1: λ < μ
- For M/M/c: λ < cμ
- Ensure proper configurations to avoid overflow or under-utilization of resources.

## Future Extensions
- Integration of machine learning algorithms for predictive analytics.
- Mobile app version for on-the-go access.
- Support for additional queuing models.
- Enhanced reporting features including visualization customizations.

---
Developed by akselsjunjun-maker
