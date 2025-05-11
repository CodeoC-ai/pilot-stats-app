import os, json, gzip, io, boto3, streamlit as st, pandas as pd

st.set_page_config(layout="wide")

st.title("User Statistics Dashboard")
st.write("This dashboard provides insights into user statistics and conversations.")

REGION = "eu-north-1"
if "AWS_ACCESS_KEY_ID" in st.secrets:
    session = boto3.Session(
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
        region_name=REGION,
    )
else:
    st.warning(
        "AWS credentials are not provided. Please set them in Streamlit secrets."
    )
    st.stop()

s3 = session.client("s3")
DATA_BUCKET = "codeoc-dashboard-prod"
STATS_KEY = "latest/user_stats.json.gz"
CONV_KEY = "latest/user_conversations.json.gz"


# load JSON data from S3
@st.cache_data(ttl=60)
def load_s3_json(key: str) -> list[dict]:
    obj = s3.get_object(Bucket=DATA_BUCKET, Key=key)
    with gzip.GzipFile(fileobj=obj["Body"]) as gz:
        return json.loads(gz.read().decode())


# load dataframes
user_stats_df = pd.DataFrame(load_s3_json(STATS_KEY))
user_conversations_df = pd.DataFrame(load_s3_json(CONV_KEY))

# proceed if both dataframes are loaded
if not user_stats_df.empty and not user_conversations_df.empty:
    # convert date strings to datetime objects
    user_stats_df["last_login"] = pd.to_datetime(
        user_stats_df["last_login"], format="mixed", utc=True
    )
    user_conversations_df["created_at"] = pd.to_datetime(
        user_conversations_df["created_at"], format="mixed", utc=True
    )
    user_conversations_df["updated_at"] = pd.to_datetime(
        user_conversations_df["updated_at"], format="mixed", utc=True
    )

    # merge user information with conversations based on user_id
    user_conversations_df = user_conversations_df.merge(
        user_stats_df[["user_id", "email", "user_role", "workshop_id", "company_name"]],
        on="user_id",
        how="left",
    )

    # create a mapping from workshop_id to company_name for later use
    workshop_company_map = (
        user_stats_df[["workshop_id", "company_name"]]
        .drop_duplicates()
        .set_index("workshop_id")["company_name"]
        .to_dict()
    )

    # divide the page into two columns
    col1, col2 = st.columns(2)

    # left column: global stats
    with col1:
        st.header("Global Stats")

        # total number of users
        total_users = user_stats_df["user_id"].nunique()
        st.metric("Total Users", total_users)

        # total number of mechanics (users with role 'mechanic')
        if "user_role" in user_stats_df.columns:
            total_mechanics = user_stats_df[user_stats_df["user_role"] == "mechanic"][
                "user_id"
            ].nunique()
            st.metric("Total Mechanics", total_mechanics)

        # total number of workshops
        total_workshops = user_stats_df["workshop_id"].nunique()
        st.metric("Total Workshops", total_workshops)

        # total number of chats
        total_chats = len(user_conversations_df)
        st.metric("Total Chats", total_chats)

        # total number of free chats, the one with dtcs and internal_error_codes as None
        # free_chats = len(
        #     user_conversations_df[
        #         (user_conversations_df["dtcs"].isnull())
        #         & (user_conversations_df["internal_error_codes"].isnull())
        #     ]
        # )
        # st.metric("Free Chats", free_chats)

        # number of verified answers (open_search=False)
        verified_answers = len(
            user_conversations_df[user_conversations_df["open_search"] == False]
        )
        st.metric("Verified Answers", f"{verified_answers}/{total_chats}")

        # engagement: number of chats with messages length > 4
        engaged_chats = user_conversations_df[
            user_conversations_df["messages"].apply(lambda x: len(x) > 4)
        ]
        num_engaged_chats = len(engaged_chats)
        st.metric("Engaged Chats (messages > 4)", num_engaged_chats)

        # average number of messages per chat
        user_conversations_df["num_messages"] = user_conversations_df["messages"].apply(
            len
        )
        avg_messages_per_chat = user_conversations_df["num_messages"].mean()
        st.metric("Average Messages per Chat", f"{avg_messages_per_chat:.2f}")

        # active users (users who have at least one chat)
        active_users = user_conversations_df["user_id"].nunique()
        st.metric("Active Users", active_users)

        # average number of chats per user
        avg_chats_per_user = user_conversations_df.groupby("user_id").size().mean()
        st.metric("Average Chats per User", f"{avg_chats_per_user:.2f}")

        # average cost per chat
        avg_cost_per_chat = user_conversations_df["tot_cost"].mean()
        st.metric("Average Cost per Chat", f"{avg_cost_per_chat:.2f}$")

        # workshop statistics
        st.header("Workshop Statistics")
        workshop_stats = (
            user_conversations_df.groupby("workshop_id")
            .agg(
                company=("company_name", "first"),
                num_chats=("chat_id", "count"),
                avg_cost=("tot_cost", "mean"),
                num_users=("user_id", "nunique"),
            )
            .reset_index()
        )
        workshop_stats = workshop_stats.sort_values(by="num_chats", ascending=False)
        st.write(workshop_stats)

        # calculate feedback statistics
        st.header("Feedback Analysis")

        # calculate feedback sum and create a new column for thumbs up/down
        user_conversations_df["feedback_sum"] = user_conversations_df["feedback"].apply(
            lambda x: sum(x) if isinstance(x, list) else 0
        )
        user_conversations_df["thumb"] = user_conversations_df["feedback_sum"].apply(
            lambda x: "up" if x > 0 else ("down" if x < 0 else "neutral")
        )
        # total requests for supported and unsupported cars
        total_supported_requests = len(
            user_conversations_df[user_conversations_df["open_search"] == False]
        )
        total_unsupported_requests = len(
            user_conversations_df[user_conversations_df["open_search"] == True]
        )
        # count thumbs up/down for supported and unsupported cars
        supported_positive = len(
            user_conversations_df[
                (user_conversations_df["open_search"] == False)
                & (user_conversations_df["thumb"] == "up")
            ]
        )
        supported_negative = len(
            user_conversations_df[
                (user_conversations_df["open_search"] == False)
                & (user_conversations_df["thumb"] == "down")
            ]
        )
        unsupported_positive = len(
            user_conversations_df[
                (user_conversations_df["open_search"] == True)
                & (user_conversations_df["thumb"] == "up")
            ]
        )
        unsupported_negative = len(
            user_conversations_df[
                (user_conversations_df["open_search"] == True)
                & (user_conversations_df["thumb"] == "down")
            ]
        )
        # calculate ratios in percentages
        supported_positive_ratio = (
            (supported_positive / total_supported_requests * 100)
            if total_supported_requests > 0
            else 0
        )
        supported_negative_ratio = (
            (supported_negative / total_supported_requests * 100)
            if total_supported_requests > 0
            else 0
        )
        unsupported_positive_ratio = (
            (unsupported_positive / total_unsupported_requests * 100)
            if total_unsupported_requests > 0
            else 0
        )
        unsupported_negative_ratio = (
            (unsupported_negative / total_unsupported_requests * 100)
            if total_unsupported_requests > 0
            else 0
        )
        # create DataFrame for display
        feedback_matrix = pd.DataFrame(
            {
                "Supported Cars": [
                    f"{supported_positive_ratio:.1f}%",
                    f"{supported_negative_ratio:.1f}%",
                ],
                "Unsupported Cars": [
                    f"{unsupported_positive_ratio:.1f}%",
                    f"{unsupported_negative_ratio:.1f}%",
                ],
            },
            index=["👍", "👎"],
        )
        # display matrix
        st.write(feedback_matrix)
        # calculate and display percentages
        total_supported = supported_positive + supported_negative
        total_unsupported = unsupported_positive + unsupported_negative
        if total_supported > 0:
            supported_satisfaction = (supported_positive / total_supported) * 100
            st.write(
                f"Satisfaction rate for supported cars: {supported_satisfaction:.0f}%"
            )
        if total_unsupported > 0:
            unsupported_satisfaction = (unsupported_positive / total_unsupported) * 100
            st.write(
                f"Satisfaction rate for unsupported cars: {unsupported_satisfaction:.0f}%"
            )

        # most common error codes
        st.header("Most Common Error Codes")
        all_dtcs = [
            dtc
            for dtcs in user_conversations_df["dtcs"]
            if dtcs is not None
            for dtc in dtcs
        ]
        dtc_counts = pd.Series(all_dtcs).value_counts()
        st.write(dtc_counts)

        # most common internal error codes
        st.header("Most Common Internal Error Codes")
        internal_dtcs = [
            internal_error_code
            for internal_error_codes in user_conversations_df["internal_error_codes"]
            if internal_error_codes is not None
            for internal_error_code in internal_error_codes
        ]
        internal_dtc_counts = pd.Series(internal_dtcs).value_counts()
        st.write(internal_dtc_counts)

        # most common manufacturers
        st.header("Most Common Manufacturers")
        manufacturer_counts = user_conversations_df["manufacturer"].value_counts()
        st.write(manufacturer_counts)

        # most common car models
        st.header("Most Common Car Models")
        model_manufacturer_counts = (
            user_conversations_df.groupby(["manufacturer", "model"])
            .size()
            .reset_index(name="count")
        )
        model_manufacturer_counts = model_manufacturer_counts.sort_values(
            by="count", ascending=False
        )
        model_manufacturer_counts = model_manufacturer_counts.reset_index(drop=True)
        model_manufacturer_counts.index = model_manufacturer_counts.index + 1
        st.write(model_manufacturer_counts)

        # most active users
        st.header("Most Active Users")
        # date range filter for last login
        min_login_date = user_stats_df["last_login"].min().date()
        max_login_date = user_stats_df["last_login"].max().date()
        col_login_start, col_login_end = st.columns(2)
        with col_login_start:
            start_date_login = st.date_input(
                "Last login after",
                value=min_login_date,
                min_value=min_login_date,
                max_value=max_login_date,
            )
        with col_login_end:
            end_date_login = st.date_input(
                "Last login before",
                value=max_login_date,
                min_value=min_login_date,
                max_value=max_login_date,
            )
        # ensure start_date is before or same as end_date
        if start_date_login > end_date_login:
            st.error(
                "Error: 'Last login after' date must be before or same as 'Last login before' date."
            )
            # visualize table normally
            user_chat_counts_display = (
                user_conversations_df.groupby(
                    ["user_id", "email", "user_role", "company_name"]
                )
                .size()
                .reset_index(name="number of chats")
            )
            user_chat_counts_display = user_chat_counts_display.sort_values(
                by="number of chats", ascending=False
            )
            user_chat_counts_display.index = user_chat_counts_display.index + 1
        else:
            # merge user_chat_counts with user_stats_df to get last_login
            user_chat_counts_intermediate = (
                user_conversations_df.groupby(
                    ["user_id", "email", "user_role", "company_name"]
                )
                .size()
                .reset_index(name="number of chats")
            )
            # merge with last_login from user_stats_df
            user_chat_counts_with_login = pd.merge(
                user_chat_counts_intermediate,
                user_stats_df[["user_id", "last_login"]],
                on="user_id",
                how="left",
            )
            # convert start_date_login and end_date_login to datetime64[ns, UTC] to match last_login's dtype for proper comparison
            start_datetime_login = pd.to_datetime(start_date_login, utc=True)
            # add one day to end_date_login and convert to make the range inclusive of the end_date
            end_datetime_login = pd.to_datetime(
                end_date_login, utc=True
            ) + pd.Timedelta(days=1)
            # filter by last_login date
            user_chat_counts_display = user_chat_counts_with_login[
                (user_chat_counts_with_login["last_login"] >= start_datetime_login)
                & (user_chat_counts_with_login["last_login"] < end_datetime_login)
            ]
            user_chat_counts_display = user_chat_counts_display.sort_values(
                by="number of chats", ascending=False
            )
            # user_chat_counts_display = user_chat_counts_display.drop(columns=['last_login']) # drop last_login column
            user_chat_counts_display.index = user_chat_counts_display.index + 1
        st.write(user_chat_counts_display)

    # right column: company -> user -> chats hierarchy
    with col2:
        st.header("Select a Company")
        companies = user_stats_df["company_name"].unique().tolist()
        selected_company = st.selectbox("Choose a company", companies)

        if selected_company:
            # filter users by selected company
            company_users = user_stats_df[
                user_stats_df["company_name"] == selected_company
            ]

            st.subheader(f"Users at {selected_company}")
            st.write(f"Workshop ID: {company_users['workshop_id'].iloc[0]}")

            # select a user from this company
            company_user_ids = company_users["user_id"].tolist()
            company_users_options = company_users.apply(
                lambda row: f"{row['user_id']} ({row['user_role']})", axis=1
            ).tolist()
            selected_user_option = st.selectbox("Choose a user", company_users_options)

            if selected_user_option:
                # extract user_id from selected option
                selected_user_id = selected_user_option.split(" (")[0]
                selected_user_stats = company_users[
                    company_users["user_id"] == selected_user_id
                ].iloc[0]
                selected_email = selected_user_stats["email"]

                # display user information
                st.subheader(f"Stats for {selected_user_id}")
                st.write(f"**Email:** {selected_email}")
                st.write(f"**User Role:** {selected_user_stats['user_role']}")
                st.write(f"**Login History:**")
                if (
                    isinstance(selected_user_stats["login_history"], list)
                    and selected_user_stats["login_history"]
                ):
                    # convert timestamps to a readable format and sort by most recent first
                    formatted_logins = []
                    for timestamp in selected_user_stats["login_history"]:
                        try:
                            login_dt = pd.to_datetime(timestamp, utc=True)
                            formatted_logins.append(
                                {
                                    "date": login_dt.strftime("%Y-%m-%d"),
                                    "time": login_dt.strftime("%H:%M:%S"),
                                    "day": login_dt.strftime("%A"),
                                    "timestamp": login_dt,  # keep original for sorting
                                }
                            )
                        except:
                            continue
                    # sort by most recent first
                    formatted_logins = sorted(
                        formatted_logins, key=lambda x: x["timestamp"], reverse=True
                    )
                    # create a DataFrame for display
                    if formatted_logins:
                        login_df = pd.DataFrame(formatted_logins)
                        login_df = login_df[
                            ["date", "day", "time"]
                        ]  # remove timestamp column used for sorting
                        st.dataframe(login_df, hide_index=True)
                        # show summary stats
                        first_login = formatted_logins[-1]["date"]
                        last_login = formatted_logins[0]["date"]
                        st.caption(
                            f"First login: {first_login} • Recent login: {last_login} • Total logins: {len(formatted_logins)}"
                        )
                    else:
                        st.write("No login history available.")
                else:
                    st.write("No login history available.")

                # get conversations for this user
                user_conversations = user_conversations_df[
                    user_conversations_df["user_id"] == selected_user_id
                ]

                # select a chat
                st.subheader("Select a Chat")

                # display chats if available
                if len(user_conversations) > 0:
                    user_conversations = user_conversations.sort_values(
                        by="updated_at", ascending=False
                    )
                    # create a list of unique labels combining formatted updated_at, title, and chat_id for dropdown
                    chat_options = user_conversations.apply(
                        lambda row: f"{row['updated_at'].strftime('%Y-%m-%d %H:%M')} - {row['title']} (ID: {row['chat_id']})",
                        axis=1,
                    ).tolist()

                    selected_chat_option = st.selectbox("Select a chat", chat_options)
                    if selected_chat_option:
                        # extract chat_id from selected option
                        selected_chat_id = selected_chat_option.split(" (ID: ")[1][:-1]
                        # filter the selected chat using chat_id
                        selected_chat = user_conversations[
                            user_conversations["chat_id"] == selected_chat_id
                        ].iloc[0]

                        # display chat details
                        st.subheader(f"Chat: {selected_chat['title']}")
                        st.write(
                            f"**Chat ID:** {selected_chat['chat_id']}_{selected_chat['user_id']}"
                        )
                        st.write(
                            f"**Created At:** {selected_chat['created_at'].strftime('%b %d, %Y at %I:%M %p')}"
                        )
                        st.write(
                            f"**Updated At:** {selected_chat['updated_at'].strftime('%b %d, %Y at %I:%M %p')}"
                        )
                        st.write(f"**Verified:** {not(selected_chat['open_search'])}")
                        st.write(f"**Total Cost:** {selected_chat['tot_cost']}$")
                        st.write(f"**REGNO:** {selected_chat['regno']}")
                        st.write(f"**VIN:** {selected_chat['vin']}")
                        st.write("**Car Info:**")
                        if selected_chat["car_info"] is not None:
                            car_info = selected_chat["car_info"]
                            with st.expander("View car details", expanded=True):
                                col1, col2 = st.columns(2)
                                with col1:
                                    # use body_type, but fall back to model if body_type isn't available
                                    model_display = car_info.get(
                                        "body_type", car_info.get("model", "N/A")
                                    )
                                    year_value = car_info.get("year", "N/A")
                                    st.write(
                                        f"**Make/Model:** {car_info.get('make', 'N/A')} {model_display}"
                                    )
                                    st.write(
                                        f"**Year:** {int(year_value) if isinstance(year_value, (int, float)) else year_value}"
                                    )
                                    st.write(
                                        f"**Production Range:** {car_info.get('year_start', 'N/A')} - {car_info.get('year_end', 'N/A') or 'Present'}"
                                    )
                                    st.write(
                                        f"**Fuel Type:** {car_info.get('fuel_type', 'N/A')}"
                                    )
                                    st.write(f"**Mileage:** {selected_chat['mileage']}")
                                with col2:
                                    st.write(
                                        f"**Body Type:** {car_info.get('body', 'N/A')}"
                                    )
                                    st.write(
                                        f"**Body Code:** {car_info.get('body_code', 'N/A')}"
                                    )
                                    st.write(
                                        f"**Engine Type:** {car_info.get('engine_type', 'N/A')}"
                                    )
                                    # use engine_code, but fall back to engine_id if engine_code isn't available
                                    engine_code_display = car_info.get(
                                        "engine_code", car_info.get("engine_id", "N/A")
                                    )
                                    st.write(f"**Engine Code:** {engine_code_display}")
                                    st.write(
                                        f"**Engine Power:** {car_info.get('engine_power', 'N/A')}"
                                    )
                        else:
                            st.write("No car information available.")
                        if selected_chat["dtcs"] is not None:
                            st.write(f"**DTCs:** {', '.join(selected_chat['dtcs'])}")
                        if selected_chat["internal_error_codes"] is not None:
                            st.write(
                                f"**Internal Error Codes:** {', '.join(selected_chat['internal_error_codes'])}"
                            )
                        st.write(
                            f"**User description:** {selected_chat['description']}"
                        )
                        st.write(f"**Feedback:** {selected_chat['feedback']}")

                        # display messages excluding system messages
                        st.subheader("Chat Messages")
                        messages = selected_chat["messages"]
                        for message in messages:
                            if message["role"] != "system":
                                if message["role"] == "user":
                                    st.markdown(f"**User:** {message['content']}")
                                else:
                                    st.markdown(f"**Assistant:** {message['content']}")
                else:
                    st.write("No chats available for this user.")
else:
    st.warning("No data available. Please try again later.")
    st.stop()
