import pickle
import streamlit as st
import requests
import pandas as pd

# --- CONFIGURATION ---
TMDB_API_KEY = "3a9c8777be4fc606e8cf6b00aff9a86e"


# --- 1. DATA LOADING (CACHED) ---
# @st.cache_resource keeps the data in memory so it doesn't reload on every click.
# This is the most important fix for Render speed.
@st.cache_resource
def load_data():
    try:
        movies_dict = pickle.load(open('movies_dict.pkl', 'rb'))
        movies = pd.DataFrame(movies_dict)
        similarity = pickle.load(open('similarity.pkl', 'rb'))
        return movies, similarity
    except FileNotFoundError:
        st.error(
            "Error: Pickle files not found. Please make sure movies_dict.pkl and similarity.pkl are in the same folder.")
        return None, None


movies, similarity = load_data()


# --- 2. OPTIMIZED API FUNCTION ---
def fetch_movie_details(movie_id):
    # Default fallback data
    details = {
        "summary": "No summary available.",
        "rating": "N/A",
        "cast": []
    }

    try:
        # OPTIMIZATION: We use 'append_to_response=credits' to get details AND cast in ONE single request.
        # This cuts the number of API calls in half.
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&language=en-US&append_to_response=credits"

        # We removed verify=False because Render has valid SSL certificates.
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        # Extract Details
        details["summary"] = data.get("overview", "No summary available.")
        details["rating"] = data.get("vote_average", "N/A")

        # Extract Cast (Top 5)
        if "credits" in data and "cast" in data["credits"]:
            details["cast"] = [actor["name"] for actor in data["credits"]["cast"][:5]]

    except requests.exceptions.RequestException as e:
        # Silently fail or log error so the app doesn't crash
        print(f"Error fetching data for ID {movie_id}: {e}")

    return details


# --- 3. RECOMMEND FUNCTION ---
def recommend(movie):
    # Find index of the movie
    try:
        index = movies[movies['title'] == movie].index[0]
        distances = sorted(list(enumerate(similarity[index])), reverse=True, key=lambda x: x[1])

        recommended_movie_names = []
        recommended_movie_details = []

        # Loop through top 5 (skipping the first one which is the movie itself)
        for i in distances[1:6]:
            movie_id = movies.iloc[i[0]].movie_id
            movie_title = movies.iloc[i[0]].title

            recommended_movie_names.append(movie_title)

            # Fetch details
            details = fetch_movie_details(movie_id)
            recommended_movie_details.append(details)

            # OPTIMIZATION: Removed time.sleep(3).
            # TMDB allows 50 requests per second; 5 rapid requests won't ban you.
            # This saves you exactly 15 seconds of waiting time.

        return recommended_movie_names, recommended_movie_details

    except IndexError:
        st.error("Movie not found in database.")
        return [], []


# --- 4. STREAMLIT UI ---
st.set_page_config(page_title="Movie Recommender", page_icon="🎬")
st.header('🎬 Movie Recommender System')

# Check if data loaded correctly
if movies is not None and similarity is not None:
    movie_list = movies['title'].values
    selected_movie = st.selectbox("Type or select a movie from the dropdown", movie_list)

    if st.button('Show Recommendation'):
        # Add a spinner so the user knows something is happening
        with st.spinner('Fetching recommendations...'):
            names, details = recommend(selected_movie)

        if names:
            st.subheader("Recommended Movies:")
            # Display results
            for i in range(len(names)):
                with st.expander(f"**{i + 1}. {names[i]}**"):
                    # Rating Logic
                    rating = details[i]['rating']
                    rating_display = f"{rating:.1f} / 10" if isinstance(rating, (float, int)) else rating
                    st.markdown(f"**TMDb Rating:** {rating_display}")

                    st.markdown("**Summary:**")
                    st.write(details[i]['summary'])

                    st.markdown("**Starring:**")
                    st.write(", ".join(details[i]['cast']))
else:
    st.error("Could not load data. Please check your pickle files.")