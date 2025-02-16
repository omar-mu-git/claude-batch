# Claude Batch API Interface

## Overview
This project provides a user-friendly interface for managing and monitoring batch processing jobs using the Claude AI API. It enables users to submit multiple messages for processing in batches, track their status, and receive email notifications upon completion.

## Problem Statement
When working with Claude Batch API, it doesn't have an interface to create, track and retrieve message batches. 

## Solution
This application provides:
- A Streamlit-based web interface for batch submission
- Automated background monitoring of batch status
- Email notifications with formatted results
- Docker containerization for easy deployment

## Features

### 1. Batch Creation
- Submit multiple messages in a single batch
- Custom message IDs for tracking
- Support for Claude-3 models
- Batch ID generation and storage

### 2. Status Monitoring
- Automated background monitoring of batch status
- Real-time status updates
- Thread-safe batch queue management
- Configurable monitoring intervals

### 3. Result Management
- Email notifications upon batch completion
- Formatted HTML results for better readability
