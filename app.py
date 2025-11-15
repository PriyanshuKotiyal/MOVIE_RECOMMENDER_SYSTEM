import pickle
import streamlit as st
import requests
import pandas as pd
import time
import urllib3

# Disable the InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---
# 1. TMDB API KEY
# ---
TMDB_API_KEY = "3a9c8777be4fc606e8cf6b00aff9a86e"


# ---
# 2. UPDATED FUNCTION: fetch_movie_details
# ---
def fetch_movie_details(movie_id):
    """
    Fetches details (summary, rating, cast) from the TMDB API.
    """
    details = {
        "summary": "No summary found.",
        "rating": "N/A",
        "cast": []
    }

    # 1. Get Summary and Rating
    try:
        url_details = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&language=en-US"
        # --- NO PROXY ---
        response = requests.get(url_details, verify=False, timeout=5)
        response.raise_for_status()
        data = response.json()

        details["summary"] = data.get("overview", "No summary found.")
        details["rating"] = data.get("vote_average", "N/A")

    except Exception as e:
        print(f"Error fetching details for {movie_id}: {e}")
        # Continue to try fetching credits

    # 2. Get Cast (Actors/Actresses)
    try:
        url_credits = f"https://api.themoviedb.org/3/movie/{movie_id}/credits?api_key={TMDB_API_KEY}&language=en-US"
        # --- NO PROXY ---
        response_credits = requests.get(url_credits, verify=False, timeout=5)
        response_credits.raise_for_status()
        data_credits = response_credits.json()

        # Get the top 5 cast members
        if "cast" in data_credits:
            details["cast"] = [actor["name"] for actor in data_credits["cast"][:5]]

    except Exception as e:
        print(f"Error fetching credits for {movie_id}: {e}")
        details["cast"] = ["Could not load cast."]

    return details


# ---
# 3. RECOMMEND FUNCTION (No changes needed)
# ---
def recommend(movie):
    index = movies[movies['title'] == movie].index[0]
    distances = sorted(list(enumerate(similarity[index])), reverse=True, key=lambda x: x[1])

    recommended_movie_names = []
    recommended_movie_details = []

    for i in distances[1:6]:
        # Get the TMDB movie_id and title from the DataFrame
        movie_id = movies.iloc[i[0]].movie_id
        movie_title = movies.iloc[i[0]].title

        # Pass the movie_id to fetch details
        recommended_movie_names.append(movie_title)
        recommended_movie_details.append(fetch_movie_details(movie_id))

        # Keep the delay to avoid rate-limiting by the API server
        time.sleep(0.3)

    return recommended_movie_names, recommended_movie_details


# ---
# 4. STREAMLIT UI (No changes needed)
# ---
st.header('🎬 Movie Recommender System')

movies_dict = pickle.load(open('movies_dict.pkl', 'rb'))
movies = pd.DataFrame(movies_dict)
similarity = pickle.load(open('similarity.pkl', 'rb'))

movie_list = movies['title'].values
selected_movie = st.selectbox("Type or select a movie from the dropdown", movie_list)

if st.button('Show Recommendation'):

    # Get the names and details
    names, details = recommend(selected_movie)

    st.subheader("Recommended Movies:")

    # Use st.expander for each movie
    for i in range(5):
        with st.expander(f"**{i + 1}. {names[i]}**"):

            # Display Rating (and format it)
            rating = details[i]['rating']
            if isinstance(rating, (float, int)):
                st.markdown(f"**TMDb Rating:** {rating:.1f} / 10")
            else:
                st.markdown(f"**TMDb Rating:** {rating}")

            # Display Summary
            st.markdown("**Summary:**")
            st.write(details[i]['summary'])

            # Display Cast
            st.markdown("**Starring:**")
            st.write(", ".join(details[i]['cast']))