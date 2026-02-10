"""
Health Monitoring Module
========================
Multi-vitals health monitoring system with heart rate, SpO2, and temperature tracking.

Features:
- Heart Rate monitoring from Sen-11574 sensor
- SpO2 (blood oxygen) monitoring from Sen-11574 sensor
- Temperature monitoring with DS18B20 failover to Liebermeister's Rule
- Critical alert system for hypoxia (SpO2 < 90%)
- Health correlation analysis
"""

__version__ = "1.0.0"
