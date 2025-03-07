import time
import streamlit as st
import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
from batch_monitor import BatchMonitor
from database import init_db, verify_credentials, save_batch_to_db, update_batch_status, get_batch_history, get_batch_messages
import os
from dotenv import load_dotenv
import json
import datetime
init_db()

# Initialize session state variables
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "batch_id" not in st.session_state:
    st.session_state.batch_id = None
if "batch_status" not in st.session_state:
    st.session_state.batch_status = None
if "results" not in st.session_state:
    st.session_state.results = None

# Login page
def login_page():
    st.title("Login to Claude Batch API Interface")
    
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if verify_credentials(username, password):
            st.session_state.authenticated = True
            st.success("Login successful!")
            st.rerun()
        else:
            st.error("Invalid username or password")

# Main application
def main_app():
    # Initialize Anthropic client
    client = anthropic.Anthropic(
        api_key=os.getenv('ANTHROPIC_API_KEY'))
    
    st.title("Claude Batch API Interface")

    st.markdown(
        """
        This app lets you send messages using the Claude Batch API.
        • Create a new message batch and copy the Batch ID.
        • Or enter a saved Batch ID to track and retrieve its status/results.
        """
    )

    # ----------------- SECTION 1: MANAGE BATCH ID INPUT -----------------
    with st.expander("Batch ID Management"):
        st.markdown("If you already have a Batch ID saved, enter it below. Otherwise, create a new batch.")
        manual_batch_id = st.text_input("Enter Batch ID (if available)", value="")

        if manual_batch_id:
            st.session_state.batch_id = manual_batch_id.strip()
            st.success(f"Using provided Batch ID: {st.session_state.batch_id}")

    # ----------------- SECTION 2: CREATE NEW BATCH -----------------
    with st.expander("1. Create New Batch"):
        st.markdown("Enter one or more messages to create a new batch. Once submitted, your Batch ID will be shown so you can copy and save it.")

        create_new_batch = st.checkbox("I want to create a new batch")
        if create_new_batch:
            num_messages = st.number_input("How many messages do you want to send?", min_value=1, max_value=10, value=2, step=1)
            message_inputs = {}
            for i in range(int(num_messages)):
                message_inputs[f"message_{i}"] = st.text_area(f"Message {i+1}", key=f"msg_{i}", value=f"Hello, this is message {i+1}")

            if st.button("Submit Batch Creation"):
                requests = []
                for i, message in enumerate(message_inputs.values()):
                    requests.append(
                        Request(
                            custom_id=f"message-{i}",
                            params=MessageCreateParamsNonStreaming(
                                model="claude-3-5-sonnet-20241022",
                                max_tokens=1024,
                                messages=[
                                    {
                                        "role": "user",
                                        "content": message,
                                    }
                                ],
                            ),
                        )
                    )
                try:
                    message_batch = client.messages.batches.create(requests=requests)
                    if message_batch.id:
                        monitor = BatchMonitor()
                        monitor.add_batch(message_batch.id)
                    st.session_state.batch_id = message_batch.id
                    st.session_state.batch_status = message_batch.processing_status
                    st.success("Batch created successfully!")
                    st.info(f"Batch ID: {message_batch.id}\n\nCopy this ID for future reference.")
                    st.text_input("Copy Batch ID", value=message_batch.id, key="copy_batch_id")
                    
                    # Save batch to database
                    save_batch_to_db(message_batch.id, json.dumps(requests))
                except Exception as e:
                    st.error(f"Error creating batch: {e}")

    # ----------------- SECTION 3: TRACK BATCH STATUS -----------------
    with st.expander("2. Track Batch Status"):
        if st.session_state.batch_id is None:
            st.info("No Batch ID provided or created yet.")
        else:
            st.write(f"Batch ID: {st.session_state.batch_id}")

        if st.button("Refresh Batch Status"):
            try:
                message_batch = client.messages.batches.retrieve(st.session_state.batch_id)
                st.session_state.batch_status = message_batch.processing_status
                st.write(f"Current Processing Status: {message_batch.processing_status}")
                
                # Update batch status in database
                update_batch_status(st.session_state.batch_id, message_batch.processing_status)
            except Exception as e:
                st.error(f"Error retrieving batch status: {e}")

    # ----------------- SECTION 4: RETRIEVE RESULTS -----------------
    with st.expander("3. Retrieve Batch Results"):
        if st.session_state.batch_id is None:
            st.info("No Batch ID provided or created yet.")
        else:
            if st.session_state.batch_status != "ended":
                st.warning("Batch processing is not ended yet. Ensure the batch is complete before retrieving results.")
            else:
                if st.button("Retrieve Results"):
                    try:
                        results = []
                        for result in client.messages.batches.results(st.session_state.batch_id):
                            results.append(result)
                        st.session_state.results = results
                        st.success("Results retrieved successfully!")
                    except Exception as e:
                        st.error(f"Error retrieving results: {e}")

                if st.session_state.results is not None:
                    st.markdown("### Batch Results")
                    for result in st.session_state.results:
                        custom_id = result.custom_id
                        result_type = result.result.type
                        if result_type == "succeeded":
                            st.write(f"✅ {custom_id}: Success")
                            st.json(result.result.message)
                        elif result_type == "errored":
                            st.write(f"❌ {custom_id}: Error")
                            st.json(result.result.error)
                        elif result_type == "canceled":
                            st.write(f"⚠️ {custom_id}: Canceled")
                        elif result_type == "expired":
                            st.write(f"⌛ {custom_id}: Expired")
                        else:
                            st.write(f"{custom_id}: Unknown result type: {result_type}")
                            

    # ----------------- SECTION 5: BATCH HISTORY -----------------
    with st.expander("4. Batch History"):
        st.markdown("### Previous Batches")
        
        if st.button("Refresh Batch History"):
            st.rerun()
            
        batches = get_batch_history()
        
        if not batches:
            st.info("No batch history found.")
        else:
            # Create a table for batch history
            for batch in batches:
                with st.container():
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        st.markdown(f"**Batch ID:** {batch['batch_id']}")
                    with col2:
                        status_color = "green" if batch['status'] == "ended" else "orange"
                        st.markdown(f"**Status:** <span style='color:{status_color}'>{batch['status']}</span>", unsafe_allow_html=True)
                    with col3:
                        created_at = datetime.datetime.strptime(batch['created_at'].split('.')[0], '%Y-%m-%d %H:%M:%S')                        
                        st.markdown(f"**Created:** {created_at.strftime('%Y-%m-%d %H:%M')}")
                    
                    # Use this batch button
                    if st.button(f"Use this batch", key=f"use_{batch['batch_id']}"):
                        st.session_state.batch_id = batch['batch_id']
                        st.session_state.batch_status = batch['status']
                        st.success(f"Now using batch {batch['batch_id']}")
                        st.rerun()
                    
                    # Show messages
                    st.markdown("**Messages:**")
                    messages = json.loads(batch['messages']) if isinstance(batch['messages'], str) else batch['messages']
                    if messages:
                        messages_list = messages[0]['params']['messages']
                        for j, message in enumerate(messages_list):
                            st.markdown(f"**Message {j+1}:**")
                            st.text_area(f"Content", value=message['content'], height=100, key=f"hist_msg_{batch['batch_id']}_{j}", disabled=True)
                    else:
                        st.info("No messages stored for this batch.")
                    
                    st.markdown("---")

def logout():
    st.session_state.authenticated = False
    st.rerun()

# Main app flow
if st.session_state.authenticated:
    # Add logout button in sidebar
    if st.sidebar.button("Logout"):
        logout()
    
    # Show the main application
    main_app()
else:
    # Show login page
    login_page()