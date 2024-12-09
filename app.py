import streamlit as st
import pandas as pd
import json

st.set_page_config(layout="wide")

st.title("Mechanic Conversations Dashboard")

# upload user_stats.json
user_stats_file = st.file_uploader("Upload user_stats.json", type="json")
if user_stats_file:
    user_stats = json.load(user_stats_file)
    user_stats_df = pd.DataFrame(user_stats)

# upload user_conversations.json
user_conversations_file = st.file_uploader("Upload user_conversations.json", type="json")
if user_conversations_file:
    user_conversations = json.load(user_conversations_file)
    user_conversations_df = pd.DataFrame(user_conversations)

# proceed if both files are uploaded
if user_stats_file and user_conversations_file:
    # convert date strings to datetime objects
    user_stats_df['last_login'] = pd.to_datetime(user_stats_df['last_login'], format='mixed', utc=True)
    user_conversations_df['created_at'] = pd.to_datetime(user_conversations_df['created_at'], format='mixed', utc=True)
    user_conversations_df['updated_at'] = pd.to_datetime(user_conversations_df['updated_at'], format='mixed', utc=True)

    # divide the page into two columns
    col1, col2 = st.columns(2)

    # left column: global stats
    with col1:
        st.header("Global Stats")

        # total number of mechanics
        total_mechanics = user_stats_df['email'].nunique()
        st.metric("Total Mechanics", total_mechanics)

        # total number of chats
        total_chats = len(user_conversations_df)
        st.metric("Total Chats", total_chats)

        # total number of free chats, the one with dtcs and internal_error_codes as None
        free_chats = len(user_conversations_df[(user_conversations_df['dtcs'].isnull()) & (user_conversations_df['internal_error_codes'].isnull())])
        st.metric("Free Chats", free_chats)

        # number of verified answers (open_search=False)
        verified_answers = len(user_conversations_df[user_conversations_df['open_search'] == False])
        st.metric("Verified Answers", f"{verified_answers}/{total_chats}")

        # engagement: number of chats with messages length > 4
        engaged_chats = user_conversations_df[user_conversations_df['messages'].apply(lambda x: len(x) > 4)]
        num_engaged_chats = len(engaged_chats)
        st.metric("Engaged Chats (messages > 4)", num_engaged_chats)

        # average number of messages per chat
        user_conversations_df['num_messages'] = user_conversations_df['messages'].apply(len)
        avg_messages_per_chat = user_conversations_df['num_messages'].mean()
        st.metric("Average Messages per Chat", f"{avg_messages_per_chat:.2f}")

        # active mechanics (mechanics who have at least one chat)
        active_mechanics = user_conversations_df['email'].nunique()
        st.metric("Active Mechanics", active_mechanics)

        # average number of chats per mechanic
        avg_chats_per_mechanic = user_conversations_df.groupby('email').size().mean()
        st.metric("Average Chats per Mechanic", f"{avg_chats_per_mechanic:.2f}")

        # average cost per chat
        avg_cost_per_chat = user_conversations_df['tot_cost'].mean()
        st.metric("Average Cost per Chat", f"{avg_cost_per_chat:.2f}$")

        # calculate feedback statistics
        st.header("Feedback Analysis")

        # calculate feedback sum and create a new column for thumbs up/down
        user_conversations_df['feedback_sum'] = user_conversations_df['feedback'].apply(lambda x: sum(x) if isinstance(x, list) else 0)
        user_conversations_df['thumb'] = user_conversations_df['feedback_sum'].apply(lambda x: 'up' if x > 0 else ('down' if x < 0 else 'neutral'))
        # total requests for supported and unsupported cars
        total_supported_requests = len(user_conversations_df[user_conversations_df['open_search'] == False])
        total_unsupported_requests = len(user_conversations_df[user_conversations_df['open_search'] == True])
        # count thumbs up/down for supported and unsupported cars
        supported_positive = len(user_conversations_df[(user_conversations_df['open_search'] == False) & (user_conversations_df['thumb'] == 'up')])
        supported_negative = len(user_conversations_df[(user_conversations_df['open_search'] == False) & (user_conversations_df['thumb'] == 'down')])
        unsupported_positive = len(user_conversations_df[(user_conversations_df['open_search'] == True) & (user_conversations_df['thumb'] == 'up')])
        unsupported_negative = len(user_conversations_df[(user_conversations_df['open_search'] == True) & (user_conversations_df['thumb'] == 'down')])
        # calculate ratios in percentages
        supported_positive_ratio = (supported_positive / total_supported_requests * 100) if total_supported_requests > 0 else 0
        supported_negative_ratio = (supported_negative / total_supported_requests * 100) if total_supported_requests > 0 else 0
        unsupported_positive_ratio = (unsupported_positive / total_unsupported_requests * 100) if total_unsupported_requests > 0 else 0
        unsupported_negative_ratio = (unsupported_negative / total_unsupported_requests * 100) if total_unsupported_requests > 0 else 0
        # create DataFrame for display
        feedback_matrix = pd.DataFrame({
            'Supported Cars': [f"{supported_positive_ratio:.1f}%", f"{supported_negative_ratio:.1f}%"],
            'Unsupported Cars': [f"{unsupported_positive_ratio:.1f}%", f"{unsupported_negative_ratio:.1f}%"]
        }, index=['👍', '👎'])
        # display matrix
        st.write(feedback_matrix)
        # calculate and display percentages
        total_supported = supported_positive + supported_negative
        total_unsupported = unsupported_positive + unsupported_negative
        if total_supported > 0:
            supported_satisfaction = (supported_positive / total_supported) * 100
            st.write(f"Satisfaction rate for supported cars: {supported_satisfaction:.0f}%")
        if total_unsupported > 0:
            unsupported_satisfaction = (unsupported_positive / total_unsupported) * 100
            st.write(f"Satisfaction rate for unsupported cars: {unsupported_satisfaction:.0f}%")

        # most common error codes
        st.header("Most Common Error Codes")
        all_dtcs = [dtc for dtcs in user_conversations_df['dtcs'] if dtcs is not None for dtc in dtcs]
        dtc_counts = pd.Series(all_dtcs).value_counts()
        st.write(dtc_counts)

        # most common internal error codes
        st.header("Most Common Internal Error Codes")
        internal_dtcs = [internal_error_code for internal_error_codes in user_conversations_df['internal_error_codes'] if internal_error_codes is not None for internal_error_code in internal_error_codes]
        internal_dtc_counts = pd.Series(internal_dtcs).value_counts()
        st.write(internal_dtc_counts)

        # most common manufacturers
        st.header("Most Common Manufacturers")
        manufacturer_counts = user_conversations_df['manufacturer'].value_counts()
        st.write(manufacturer_counts)

        # most common car models
        st.header("Most Common Car Models")
        model_manufacturer_counts = user_conversations_df.groupby(['manufacturer', 'model']).size().reset_index(name='count')
        model_manufacturer_counts = model_manufacturer_counts.sort_values(by='count', ascending=False)
        model_manufacturer_counts = model_manufacturer_counts.reset_index(drop=True)
        model_manufacturer_counts.index = model_manufacturer_counts.index + 1
        st.write(model_manufacturer_counts)

        # most active mechanics
        st.header("Most Active Mechanics")
        mechanic_chat_counts = user_conversations_df.groupby('email').size().sort_values(ascending=False)
        mechanic_chat_counts = mechanic_chat_counts.reset_index(name='number of chats')
        mechanic_chat_counts.index = mechanic_chat_counts.index + 1
        st.write(mechanic_chat_counts)

    # right column: mechanic stats and chats
    with col2:
        st.header("Select a Mechanic")
        mechanics = user_stats_df['email'].unique()
        selected_mechanic = st.selectbox("Choose a mechanic", mechanics)

        if selected_mechanic:
            mechanic_stats = user_stats_df[user_stats_df['email'] == selected_mechanic].iloc[0]
            mechanic_conversations = user_conversations_df[user_conversations_df['email'] == selected_mechanic]

            st.subheader(f"Stats for {selected_mechanic}")

            # display mechanic stats
            st.write(f"**Last Login:** {mechanic_stats['last_login']}")
            st.write(f"**Login Count:** {int(mechanic_stats['login_count'])}")
            st.write(f"**Login History:**")
            st.write(mechanic_stats['login_history'])

            # select a chat
            st.subheader("Select a Chat")

            # display chats if available
            if len(mechanic_conversations) > 0:
                mechanic_conversations = mechanic_conversations.sort_values(by='updated_at', ascending=False)
                # create a list of unique labels combining formatted updated_at, title, and chat_id for the dropdown
                chat_options = mechanic_conversations.apply(
                    lambda row: f"{row['updated_at'].strftime('%Y-%m-%d %H:%M')} - {row['title']} (ID: {row['chat_id']})", axis=1
                ).tolist()

                selected_chat_option = st.selectbox("Select a chat", chat_options)
                if selected_chat_option:
                    # extract chat_id from the selected option
                    selected_chat_id = selected_chat_option.split(" (ID: ")[1][:-1]
                    # filter the selected chat using chat_id
                    selected_chat = mechanic_conversations[mechanic_conversations['chat_id'] == selected_chat_id].iloc[0]

                    # display chat details
                    st.subheader(f"Chat: {selected_chat['title']}")
                    st.write(f"**Created At:** {selected_chat['created_at']}")
                    st.write(f"**Updated At:** {selected_chat['updated_at']}")
                    st.write(f"**Verified:** {not(selected_chat['open_search'])}")
                    st.write(f"**Total Cost:** {selected_chat['tot_cost']}$")
                    st.write(f"**REGNO:** {selected_chat['regno']}")
                    st.write(f"**Vehicle:** {selected_chat['manufacturer']} {selected_chat['model']} {int(selected_chat['year'])}")
                    st.write(f"**Mileage:** {selected_chat['mileage']}")
                    st.write(f"**Error Codes:** {', '.join(selected_chat['dtcs'])}")
                    st.write(f"**Internal Error Codes:** {', '.join(selected_chat['internal_error_codes'])}")
                    st.write(f"**Mechanic description:** {selected_chat['description']}")
                    st.write(f"**Feedback:** {selected_chat['feedback']}")

                    # display messages excluding system messages
                    st.write("**Messages:**")
                    messages = selected_chat['messages']
                    for message in messages:
                        if message['role'] != 'system':
                            if message['role'] == 'user':
                                st.markdown(f"**User:** {message['content']}")
                            else:
                                st.markdown(f"**Assistant:** {message['content']}")
            else:
                st.write("No chats available for this mechanic.")
