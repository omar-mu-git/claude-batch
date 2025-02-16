import schedule
import time
import anthropic
import logging
from datetime import datetime
from queue import Queue
import threading
import smtplib
import os
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('batch_monitor.log'),
        logging.StreamHandler()
    ]
)

class BatchMonitor:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.initialized = False
            return cls._instance

    def __init__(self):
        if self.initialized:
            return
        load_dotenv()
        
        self.batch_queue = Queue()
        self.client = anthropic.Anthropic(
            api_key=os.getenv('ANTHROPIC_API_KEY')
        )
        self.active_batches = {}
        
        self.smtp_server = os.getenv('SMTP_SERVER')
        self.smtp_port = int(os.getenv('SMTP_PORT'))
        self.sender_email = os.getenv('SENDER_EMAIL')
        self.sender_password = os.getenv('SENDER_PASSWORD')
        self.recipient_email = os.getenv('RECIPIENT_EMAIL')

        self.monitor_thread = threading.Thread(target=self.run_monitor, daemon=True)
        self.monitor_thread.start()
        
        self.initialized = True

    def add_batch(self, batch_id):
        """Add a new batch to monitor"""
        self.batch_queue.put(batch_id)
        logging.info(f"Added batch {batch_id} to monitoring queue")

    def process_queue(self):
        """Process any new batches in the queue"""
        while not self.batch_queue.empty():
            batch_id = self.batch_queue.get()
            if batch_id not in self.active_batches:
                self.active_batches[batch_id] = None
                logging.info(f"Batch {batch_id} added to active monitoring")

    def check_batch_status(self):
        """Check status of all active batches"""
        self.process_queue()  # Process any new batches first
        
        completed_batches = []
        for batch_id in self.active_batches.keys():
            try:
                message_batch = self.client.messages.batches.retrieve(batch_id)
                current_status = message_batch.processing_status
                previous_status = self.active_batches[batch_id]

                if current_status != previous_status:
                    logging.info(f"Batch {batch_id} status changed from {previous_status} to {current_status}")
                    self.active_batches[batch_id] = current_status

                if current_status == "ended":
                    logging.info(f"Batch {batch_id} has completed")
                    completed_batches.append(batch_id)
                    self.handle_completed_batch(batch_id)

            except Exception as e:
                logging.error(f"Error checking batch {batch_id}: {e}")

        # Remove completed batches from monitoring
        for batch_id in completed_batches:
            del self.active_batches[batch_id]

    def run_monitor(self):
        """Run the monitoring loop"""
        schedule.every(5).minutes.do(self.check_batch_status)
        
        # Do an initial check right away
        self.check_batch_status()
        
        while True:
            schedule.run_pending()
            time.sleep(60)

    def format_message_content(self, content) -> str:
        """Format the message content with preserved formatting"""
        if isinstance(content, list):
            formatted_content = ""
            for block in content:
                if hasattr(block, 'text'):
                    # Preserve line breaks and format them as HTML
                    text = block.text.replace('\n', '<br>')
                    # Preserve indentation (spaces at start of lines)
                    text = text.replace('  ', '&nbsp;&nbsp;')
                    # Add paragraph styling
                    formatted_content += f'<p style="margin: 8px 0;">{text}</p>'
                else:
                    formatted_content += f'<p>{str(block)}</p>'
            return formatted_content
        return str(content)

    def format_batch_results(self, results) -> str:
        """Format batch results into readable HTML with better styling"""
        html_content = """
        <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
            <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                Batch Processing Results
            </h2>
        """
        
        for idx, result in enumerate(results, 1):
            html_content += f"""
            <div style="margin: 20px 0;">
                <h3 style="color: #2c3e50; margin-bottom: 10px;">
                    Message {idx} (ID: {result.custom_id})
                </h3>
            """
            
            if result.result.type == "succeeded":
                message = result.result.message
                html_content += f"""
                <div style="background-color: #f8f9fa; border-left: 4px solid #2ecc71; 
                            padding: 15px; border-radius: 4px; margin: 10px 0;">
                    <div style="margin-bottom: 10px;">
                        <strong style="color: #2c3e50;">Message ID:</strong> 
                        <span style="color: #7f8c8d;">{message.id}</span>
                    </div>
                    <div style="background-color: white; padding: 15px; border-radius: 4px; 
                                margin-top: 10px; line-height: 1.6;">
                        <strong style="color: #2c3e50; display: block; margin-bottom: 10px;">
                            Content:
                        </strong>
                        <div style="color: #34495e;">
                            {self.format_message_content(message.content)}
                        </div>
                    </div>
                </div>
                """
            elif result.result.type == "errored":
                html_content += f"""
                <div style="background-color: #fff5f5; border-left: 4px solid #e74c3c; 
                            padding: 15px; border-radius: 4px; margin: 10px 0;">
                    <strong style="color: #c0392b;">Error:</strong> 
                    <span style="color: #7f8c8d;">{result.result.error}</span>
                </div>
                """
            else:
                html_content += f"""
                <div style="background-color: #fff9e6; border-left: 4px solid #f1c40f; 
                            padding: 15px; border-radius: 4px; margin: 10px 0;">
                    <strong style="color: #f39c12;">Status:</strong> 
                    <span style="color: #7f8c8d;">{result.result.type}</span>
                </div>
                """
            
            html_content += "</div>"
        
        html_content += "</div>"
        return html_content

    def send_email_notification(self, batch_id: str, html_content: str):
        """Send email notification with formatted results"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'Batch Processing Complete - {batch_id}'
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email

            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
                
            logging.info(f"Email notification sent for batch {batch_id}")
            
        except Exception as e:
            logging.error(f"Failed to send email notification: {e}")

    def handle_completed_batch(self, batch_id):
        """Handle completed batch by sending email notification"""
        try:
            # Retrieve results
            results = list(self.client.messages.batches.results(batch_id))
            
            # Format results
            html_content = self.format_batch_results(results)
            
            # Send email notification
            self.send_email_notification(batch_id, html_content)
            
            logging.info(f"Successfully processed completed batch {batch_id}")
            
        except Exception as e:
            logging.error(f"Error handling completed batch {batch_id}: {e}")
            
    def add_batch(self, batch_id):
        """Add a new batch to monitor"""
        self.active_batches[batch_id] = None
        logging.info(f"Added batch {batch_id} to monitoring")

    def check_batch_status(self):
        """Check status of all active batches"""
        completed_batches = []

        for batch_id in self.active_batches.keys():
            try:
                message_batch = self.client.messages.batches.retrieve(batch_id)
                current_status = message_batch.processing_status
                previous_status = self.active_batches[batch_id]

                # Log if status has changed
                if current_status != previous_status:
                    logging.info(f"Batch {batch_id} status changed from {previous_status} to {current_status}")
                    self.active_batches[batch_id] = current_status

                # If batch is complete
                if current_status == "ended":
                    logging.info(f"Batch {batch_id} has completed")
                    completed_batches.append(batch_id)
                    self.handle_completed_batch(batch_id)

            except Exception as e:
                logging.error(f"Error checking batch {batch_id}: {e}")

        # Remove completed batches from monitoring
        for batch_id in completed_batches:
            del self.active_batches[batch_id]