"use client"
import { motion } from "framer-motion"
import { Github, Youtube, BookOpen, RefreshCw, X, Briefcase } from "lucide-react"
import RecommendationCard from "../components/RecommendationCard"
import GlowButton from "../components/GlowButton"
import ProgressRing from "../components/ProgressRing"
import { Link , useLocation} from "react-router-dom"
import { useAppContext } from "../App"
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

const Dashboard = () => {
  const {
      user
    } = useAppContext()
const navigate = useNavigate();

  const userProfile = {
    name: user.name,
    avatar: "👨‍💻",
    email: user.email,
  }

  const syncStatus = {
    github: { status: "synced", lastSync: "2 min ago", progress: 95 },
    youtube: { status: "syncing", lastSync: "now", progress: 67 },
    coursera: { status: "synced", lastSync: "5 min ago", progress: 100 },
  }

const [recommendations, setRecommendations] = useState({
    github: [],
    youtube: [],
    coursera: [],
    jobs: [],
  });

// Add loading and error states for debugging
const [loading, setLoading] = useState(true);
const [error, setError] = useState(null);
const [jobsLoading, setJobsLoading] = useState(false);
const [jobsError, setJobsError] = useState(null);
const [userLocation, setUserLocation] = useState(null);

// New states for preferences modal
const [showPreferencesModal, setShowPreferencesModal] = useState(false);
const [keywordsInput, setKeywordsInput] = useState("");
const [customKeywords, setCustomKeywords] = useState([]);
const [isCustomMode, setIsCustomMode] = useState(false);
const [customLoading, setCustomLoading] = useState(false);

  useEffect(() => {
    console.log("Dashboard useEffect triggered");
    console.log("Full user object:", user);
    console.log("User email:", user?.email);
    console.log("User email type:", typeof user?.email);
    console.log("User email length:", user?.email?.length);
    
    // More flexible check for user email
    const email = user?.email || user?.Email || user?.emailAddress;
    console.log("Resolved email:", email);
    
    // Also check localStorage as fallback
    let fallbackEmail = email;
    if (!email || email.trim() === '') {
      const savedUser = localStorage.getItem('user');
      if (savedUser) {
        try {
          const parsedUser = JSON.parse(savedUser);
          fallbackEmail = parsedUser.email || parsedUser.Email || parsedUser.emailAddress;
          console.log("Using fallback email from localStorage:", fallbackEmail);
        } catch (e) {
          console.error("Error parsing saved user:", e);
        }
      }
    }
    
    if (!fallbackEmail || fallbackEmail.trim() === '') {
      console.log("No user email found, skipping fetch");
      setLoading(false);
      return;
    }

    const fetchRecommendations = async () => {
      try {
        setLoading(true);
        setError(null);
        
        console.log("Fetching recommendations for:", fallbackEmail);
        
        const [gitRes, ytRes, courseraRes] = await Promise.all([
          fetch(`http://localhost:8000/get_github_recommendations?email=${encodeURIComponent(fallbackEmail)}`),
          fetch(`http://localhost:8000/get_youtube_recommendations?email=${encodeURIComponent(fallbackEmail)}`),
          fetch(`http://localhost:8000/get_coursera_recommendations?email=${encodeURIComponent(fallbackEmail)}`),
        ]);

        console.log("GitHub response status:", gitRes.status);
        console.log("YouTube response status:", ytRes.status);
        console.log("Coursera response status:", courseraRes.status);

        // Check if responses are ok
        if (!gitRes.ok) {
          console.error("GitHub API error:", gitRes.status, gitRes.statusText);
        }
        if (!ytRes.ok) {
          console.error("YouTube API error:", ytRes.status, ytRes.statusText);
        }
        if (!courseraRes.ok) {
          console.error("Coursera API error:", courseraRes.status, courseraRes.statusText);
        }

        const [gitData, ytData, courseraData] = await Promise.all([
          gitRes.json(),
          ytRes.json(),
          courseraRes.json(),
        ]);

        console.log("Raw GitHub data:", gitData);
        console.log("Raw YouTube data:", ytData);
        console.log("Raw Coursera data:", courseraData);

        // Check if data has error property
        if (gitData.error) {
          console.error("GitHub API returned error:", gitData.error);
        }
        if (ytData.error) {
          console.error("YouTube API returned error:", ytData.error);
        }
        if (courseraData.error) {
          console.error("Coursera API returned error:", courseraData.error);
        }

        const processedRecommendations = {
          github: Array.isArray(gitData) ? gitData.map((repo, index) => ({
            id: `github-${index}-${repo.repoName}`, // Add unique ID
            title: repo.repoName,
            description: repo.description,
            stars: formatCount(repo.stars),
            forks: formatCount(repo.forks),
            language: repo.language,
            trending: Math.random() < 0.5,
            url: repo.url
          })) : [],
          youtube: Array.isArray(ytData) ? ytData.map((video, index) => ({
            id: `youtube-${index}-${video.title}`, // Add unique ID
            title: video.title,
            channel: video.channelName,
            duration: video.duration ? video.duration.replace(" seconds", "") : "N/A",
            views: formatCount(video.views),
            uploadedAgo: video.publishedAt ? getTimeAgo(video.publishedAt) : "Unknown",
            thumbnail: "🎯",
            url: video.url
          })) : [],
          coursera: Array.isArray(courseraData) ? courseraData.map((course, index) => ({
            id: `coursera-${index}-${course.title}`, // Add unique ID
            title: course.title,
            provider: course.provider,
            students:course.enrolled,
            rating: course.rating,
            duration: extractDuration(course.info || ""),
            level: extractLevel(course.info || ""),
            url: course.url,
            info: course.info
          })) : [],
          jobs: [],
        };

        console.log("Processed recommendations:", processedRecommendations);
        setRecommendations((prev) => ({
          ...processedRecommendations,
          // Preserve any jobs already fetched by the parallel jobs effect.
          jobs: prev.jobs?.length ? prev.jobs : processedRecommendations.jobs,
        }));
        
      } catch (err) {
        console.error("Failed to fetch recommendations:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchRecommendations();
  }, [user]); // Changed dependency to entire user object

// Fetch jobs in parallel with the main recommendations flow. We:
//   1. Ask ipapi.co for the user's city/region/country (best-effort).
//   2. POST that to the backend so it's persisted on the users row.
//   3. Hit /get_jobs which queries SerpApi using the user's existing
//      keyword history + the location we just stored.
// All steps are wrapped so a failure in one doesn't kill the rest —
// the backend falls back gracefully when location is missing.
useEffect(() => {
  const email = user?.email || user?.Email || user?.emailAddress;
  if (!email) return;

  let cancelled = false;

  const fetchJobs = async () => {
    try {
      setJobsLoading(true);
      setJobsError(null);

      let locationDetails = null;
      try {
        const locRes = await fetch("https://ipapi.co/json/");
        if (locRes.ok) {
          const locJson = await locRes.json();
          locationDetails = {
            email,
            city: locJson.city || null,
            region: locJson.region || null,
            country: locJson.country_name || null,
            country_code: locJson.country_code || null,
          };
          setUserLocation(locationDetails);

          // Best-effort persist; don't block on failure.
          fetch("http://localhost:8000/profile/location", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(locationDetails),
          }).catch((err) =>
            console.warn("[Jobs] failed to persist location:", err)
          );
        }
      } catch (err) {
        console.warn("[Jobs] ipapi.co lookup failed:", err);
      }

      const jobsRes = await fetch(
        `http://localhost:8000/get_jobs?email=${encodeURIComponent(email)}`
      );
      const jobsJson = await jobsRes.json();

      if (cancelled) return;

      if (jobsJson?.error) {
        console.error("[Jobs] backend error:", jobsJson.error);
        setJobsError(jobsJson.error);
        return;
      }

      const jobs = Array.isArray(jobsJson?.jobs) ? jobsJson.jobs : [];
      const mappedJobs = jobs.map((job, index) => ({
        id: `job-${index}-${job.job_id || job.title}`,
        title: job.title,
        companyName: job.company_name,
        location: job.location,
        via: job.via,
        description: job.description,
        thumbnail: job.thumbnail,
        scheduleType: job.schedule_type,
        postedAt: job.posted_at,
        url: job.apply_link || job.share_link,
      }));

      setRecommendations((prev) => ({ ...prev, jobs: mappedJobs }));
    } catch (err) {
      console.error("[Jobs] fetch failed:", err);
      if (!cancelled) setJobsError(err.message);
    } finally {
      if (!cancelled) setJobsLoading(false);
    }
  };

  fetchJobs();

  return () => {
    cancelled = true;
  };
}, [user]);


const formatCount = (num) => {
  if (num === null || num === undefined) return "0";
  const n = parseInt(num);
  if (isNaN(n)) return "0";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "k";
  return n.toString();
};

const getTimeAgo = (isoDate) => {
  try {
    const date = new Date(isoDate);
    const now = new Date();
    const diff = (now - date) / 1000;
    const days = Math.floor(diff / 86400);
    if (days < 1) return "today";
    if (days === 1) return "1 day ago";
    if (days < 7) return `${days} days ago`;
    return `${Math.floor(days / 7)} week(s) ago`;
  } catch (error) {
    console.error("Error parsing date:", isoDate, error);
    return "Unknown";
  }
};

const extractDuration = (info) => {
  const match = info.match(/\d+\s*(weeks|months)/i);
  return match ? match[0] : "Flexible";
};

const extractLevel = (info) => {
  const levels = ["Beginner", "Intermediate", "Advanced"];
  return levels.find(level => info.toLowerCase().includes(level.toLowerCase())) || "All Levels";
};

// Handle preferences modal
// Enhanced handlePreferencesSubmit function with full API integration
// Enhanced handlePreferencesSubmit function with full API integration
const handlePreferencesSubmit = async () => {
  if (!keywordsInput.trim()) return;
  
  const keywords = keywordsInput.split(',').map(keyword => keyword.trim()).filter(keyword => keyword);
  setCustomKeywords(keywords);
  setCustomLoading(true);
  setShowPreferencesModal(false);
  
  try {
    const email = user?.email || user?.Email || user?.emailAddress;
    
    if (!email) {
      console.error("No user email found");
      setCustomLoading(false);
      return;
    }

    console.log("Starting custom recommendation flow with keywords:", keywords);
    console.log("User email:", email);

    // Step 1: Get user ID from email
    const userIdResponse = await fetch(`http://localhost:8000/get_userid?email=${encodeURIComponent(email)}`);
    const userId = await userIdResponse.json();
    
    if (userIdResponse.ok && !userId.error) {
      console.log("Retrieved user ID:", userId);
      
      // Step 2: Get tokens for both platforms
      const [githubTokenResponse, youtubeTokenResponse] = await Promise.all([
        fetch(`http://localhost:8000/token?user_id=${userId}&platform=github`),
        fetch(`http://localhost:8000/token?user_id=${userId}&platform=google`)
      ]);
      
      const githubToken = await githubTokenResponse.json();
      const youtubeToken = await youtubeTokenResponse.json();
      
      console.log("Retrieved tokens - GitHub:", !!githubToken, "YouTube:", !!youtubeToken);
      
      // Step 3: Prepare UserHistory data with custom keywords
      // For GitHub/YouTube: Just the keywords as strings
      const githubYoutubeUserHistory = {
        history: keywords
      };
      
      // For Coursera: Create URLs with /learn/ pattern that the endpoint expects
      const courseraHistory = keywords.map(keyword => 
        `https://coursera.org/learn/${keyword.toLowerCase().replace(/\s+/g, '-')}-fundamentals`
      );
      
      const courseraUserHistory = {
        history: courseraHistory
      };
      
      // Step 4: Generate recommendations for all platforms
      const recommendationPromises = [];
      
      // GitHub recommendations (if token available)
      if (githubToken && !githubToken.error) {
        recommendationPromises.push(
          fetch(`http://localhost:8000/recommend-git?token=${encodeURIComponent(githubToken)}`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(githubYoutubeUserHistory)
          }).then(res => ({ platform: 'github', response: res }))
        );
      }
      
      // YouTube recommendations (if token available)
      if (youtubeToken && !youtubeToken.error) {
        recommendationPromises.push(
          fetch(`http://localhost:8000/recommend-yt?token=${encodeURIComponent(youtubeToken)}`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(githubYoutubeUserHistory)
          }).then(res => ({ platform: 'youtube', response: res }))
        );
      }
      
      // Coursera recommendations (always available)
      recommendationPromises.push(
        fetch(`http://localhost:8000/recommend-coursera?email=${encodeURIComponent(email)}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(courseraUserHistory)
        }).then(res => ({ platform: 'coursera', response: res }))
      );
      
      // Wait for all recommendation requests to complete
      const recommendationResults = await Promise.all(recommendationPromises);
      
      console.log("Recommendation generation completed");
      
      // Process results
      for (const result of recommendationResults) {
        const responseData = await result.response.json();
        console.log(`${result.platform} recommendation result:`, responseData);
        
        if (!result.response.ok) {
          console.error(`Error generating ${result.platform} recommendations:`, responseData);
        }
      }
      
      // Step 5: Wait a bit for database updates to complete
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Step 6: Fetch updated recommendations from database
      const [gitRes, ytRes, courseraRes] = await Promise.all([
        fetch(`http://localhost:8000/get_github_recommendations?email=${encodeURIComponent(email)}`),
        fetch(`http://localhost:8000/get_youtube_recommendations?email=${encodeURIComponent(email)}`),
        fetch(`http://localhost:8000/get_coursera_recommendations?email=${encodeURIComponent(email)}`),
      ]);

      const [gitData, ytData, courseraData] = await Promise.all([
        gitRes.json(),
        ytRes.json(),
        courseraRes.json(),
      ]);

      console.log("Updated recommendations fetched:");
      console.log("GitHub:", gitData);
      console.log("YouTube:", ytData);
      console.log("Coursera:", courseraData);

      // Step 7: Update state with new recommendations
      const updatedRecommendations = {
        github: Array.isArray(gitData) ? gitData.map((repo, index) => ({
          id: `custom-github-${index}-${repo.repoName}`,
          title: repo.repoName,
          description: repo.description,
          stars: formatCount(repo.stars),
          forks: formatCount(repo.forks),
          language: repo.language,
          trending: true, // Mark as trending for custom recommendations
          url: repo.url
        })) : [],
        youtube: Array.isArray(ytData) ? ytData.map((video, index) => ({
          id: `custom-youtube-${index}-${video.title}`,
          title: video.title,
          channel: video.channelName,
          duration: video.duration ? video.duration.replace(" seconds", "") : "N/A",
          views: formatCount(video.views),
          uploadedAgo: video.publishedAt ? getTimeAgo(video.publishedAt) : "Unknown",
          thumbnail: "🎯",
          url: video.url
        })) : [],
        coursera: Array.isArray(courseraData) ? courseraData.map((course, index) => ({
          id: `custom-coursera-${index}-${course.title}`,
          title: course.title,
          provider: course.provider,
          students: course.enrolled,
          rating: course.rating,
          duration: extractDuration(course.info || ""),
          level: extractLevel(course.info || ""),
          url: course.url,
          info: course.info
        })) : []
      };

      // Update the recommendations state
      setRecommendations(updatedRecommendations);
      
      // Set custom mode
      setIsCustomMode(true);
      console.log("Custom recommendations updated successfully");
      
    } else {
      console.error("Failed to get user ID:", userId);
      setError("Failed to retrieve user information. Please try again.");
    }
    
  } catch (error) {
    console.error("Error in custom recommendation flow:", error);
    setError("Failed to generate custom recommendations. Please try again.");
  } finally {
    setCustomLoading(false);
  }
};


  return (
    <div className="min-h-screen pt-24 pb-12 px-6 relative">
      <div className="container mx-auto max-w-7xl">
        {/* Debug Information - Remove in production */}
    

        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }} className="relative mb-12">
          <div className="absolute inset-0 bg-gradient-to-r from-purple-600/10 to-cyan-600/10 rounded-2xl blur-xl"></div>
          <div className="relative backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-8">
            <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
              <div className="flex items-center space-x-6">
                <motion.div className="relative" whileHover={{ scale: 1.05 }}>
                  <div className="absolute inset-0 bg-gradient-to-r from-cyan-400 to-purple-500 rounded-full blur-md opacity-75"></div>
                  <div className="relative w-20 h-20 bg-gradient-to-r from-cyan-500 to-purple-600 rounded-full flex items-center justify-center text-3xl">
                    {userProfile.avatar}
                  </div>
                </motion.div>

                <div>
                  <h1 className="text-3xl md:text-4xl font-bold text-white mb-2">
                    Welcome back,{" "}
                    <span className="bg-gradient-to-r from-cyan-400 to-purple-400 bg-clip-text text-transparent">
                      {userProfile.name}
                    </span>
                    !
                  </h1>
                  <p className="text-gray-300 text-lg">{userProfile.email}</p>
                </div>
              </div>

              <div className="flex flex-col sm:flex-row gap-4">
                 <GlowButton variant="primary" size="medium" onClick={() => navigate("/")}>
              Homepage
            </GlowButton>
                <GlowButton 
                  variant="secondary" 
                  size="medium"
                  onClick={() => setShowPreferencesModal(true)}
                >
                  {isCustomMode ? "Custom Recommendation" : "Customize Preferences"}
                </GlowButton>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Preferences Modal */}
        {showPreferencesModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="absolute inset-0 bg-black/60 backdrop-blur-md"
              onClick={() => setShowPreferencesModal(false)}
            />
            
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              className="relative w-full max-w-2xl mx-auto"
            >
              <div className="absolute inset-0 bg-gradient-to-br from-purple-600/30 to-cyan-600/30 rounded-3xl blur-2xl" />
              <div className="relative backdrop-blur-xl bg-white/10 border border-white/20 rounded-3xl p-10 shadow-2xl">
                <div className="flex items-center justify-between mb-8">
                  <h3 className="text-3xl font-bold bg-gradient-to-r from-white to-gray-300 bg-clip-text text-transparent">
                    Customize Your Preferences
                  </h3>
                  <motion.button
                    whileHover={{ scale: 1.1, rotate: 90 }}
                    whileTap={{ scale: 0.9 }}
                    onClick={() => setShowPreferencesModal(false)}
                    className="p-2 rounded-full bg-white/10 hover:bg-white/20 text-gray-400 hover:text-white transition-all duration-200"
                  >
                    <X className="w-6 h-6" />
                  </motion.button>
                </div>
                
                <div className="space-y-8">
                  <div>
                    <label className="block text-white text-lg font-medium mb-4">
                      Enter keywords that interest you
                    </label>
                    <div className="relative">
                      <input
                        type="text"
                        value={keywordsInput}
                        onChange={(e) => setKeywordsInput(e.target.value)}
                        placeholder="e.g. machine learning, react, python, web development"
                        className="w-full px-6 py-4 bg-white/10 border border-white/30 rounded-2xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500/60 focus:border-purple-500/60 backdrop-blur-sm transition-all duration-200 text-lg"
                      />
                      <div className="absolute inset-0 bg-gradient-to-r from-purple-600/20 to-cyan-600/20 rounded-2xl blur-xl opacity-0 group-focus-within:opacity-100 transition-opacity -z-10" />
                    </div>
                    <p className="text-gray-400 text-sm mt-3 ml-2">
                      💡 Separate multiple keywords with commas for better recommendations
                    </p>
                  </div>
                  
                  <div className="flex gap-6 pt-6">
                    <div className="flex-1">
                      <GlowButton
                        variant="primary"
                        size="large"
                        onClick={handlePreferencesSubmit}
                        disabled={!keywordsInput.trim()}
                        className="w-full"
                      >
                        Generate Custom Recommendations
                      </GlowButton>
                    </div>
                    <GlowButton
                      variant="secondary"
                      size="large"
                      onClick={() => setShowPreferencesModal(false)}
                    >
                      Cancel
                    </GlowButton>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        )}


        {/* Loading State */}
        {(loading || customLoading) && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
            <p className="text-white mt-4">
              {customLoading ? "Generating custom recommendations..." : "Loading recommendations..."}
            </p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-red-500/20 border border-red-500/50 rounded-lg p-4 mb-8">
            <p className="text-red-400">Error loading recommendations: {error}</p>
          </div>
        )}

        {/* GitHub Recommendations */}
        {!loading && !customLoading && (
          <motion.section
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="mb-12"
          >
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center space-x-4">
                <Github className="w-8 h-8 text-white" />
                <h2 className="text-3xl font-bold text-white">
                  {isCustomMode ? "Custom GitHub Recommendations" : "Trending Repositories"}
                </h2>
                <span className="px-3 py-1 bg-green-500/20 text-green-400 rounded-full text-sm font-medium">
                  {recommendations.github.length} items
                </span>
              </div>
            </div>

            {recommendations.github.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                <Github className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No GitHub recommendations found</p>
                <p className="text-sm mt-2">Try engaging with more content</p>
              </div>
            ) : (
              <div className="grid lg:grid-cols-3 gap-6">
                {recommendations.github.map((repo, index) => (
                  <motion.div
                    key={repo.id} // Use unique ID instead of title
                    initial={{ opacity: 0, x: -30 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.6, delay: index * 0.1 }}
                  >
                    <RecommendationCard type="github" data={repo} />
                  </motion.div>
                ))}
              </div>
            )}
          </motion.section>
        )}

        {/* YouTube Recommendations */}
        {!loading && !customLoading && (
          <motion.section
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="mb-12"
          >
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center space-x-4">
                <Youtube className="w-8 h-8 text-red-500" />
                <h2 className="text-3xl font-bold text-white">
                  {isCustomMode ? "Custom Video Recommendations" : "Recommended Videos"}
                </h2>
                <span className="px-3 py-1 bg-red-500/20 text-red-400 rounded-full text-sm font-medium">
                  {recommendations.youtube.length} items
                </span>
              </div>
            </div>

            {recommendations.youtube.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                <Youtube className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No YouTube recommendations found</p>
                <p className="text-sm mt-2">Try engaging with more content</p>
              </div>
            ) : (
              <div className="grid lg:grid-cols-3 gap-6">
                {recommendations.youtube.map((video, index) => (
                  <motion.div
                    key={video.id} // Use unique ID instead of title
                    initial={{ opacity: 0, x: -30 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.6, delay: index * 0.1 }}
                  >
                    <RecommendationCard type="youtube" data={video} />
                  </motion.div>
                ))}
              </div>
            )}
          </motion.section>
        )}

        {/* Coursera Recommendations */}
        {!loading && !customLoading && (
          <motion.section
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.5 }}
            className="mb-12"
          >
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center space-x-4">
                <BookOpen className="w-8 h-8 text-blue-500" />
                <h2 className="text-3xl font-bold text-white">
                  {isCustomMode ? "Custom Learning Paths" : "Learning Paths"}
                </h2>
                <span className="px-3 py-1 bg-blue-500/20 text-blue-400 rounded-full text-sm font-medium">
                  {recommendations.coursera.length} items
                </span>
              </div>
            </div>

            {recommendations.coursera.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                <BookOpen className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No Coursera recommendations found</p>
                <p className="text-sm mt-2">Try engaging with more content</p>
              </div>
            ) : (
              <div className="grid lg:grid-cols-3 gap-6">
                {recommendations.coursera.map((course, index) => (
                  <motion.div
                    key={course.id} // Use unique ID instead of title
                    initial={{ opacity: 0, x: -30 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.6, delay: index * 0.1 }}
                  >
                    <RecommendationCard type="coursera" data={course} />
                  </motion.div>
                ))}
              </div>
            )}
          </motion.section>
        )}

        {/* Job Recommendations */}
        {!loading && !customLoading && (
          <motion.section
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.55 }}
            className="mb-12"
          >
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center space-x-4">
                <Briefcase className="w-8 h-8 text-emerald-400" />
                <h2 className="text-3xl font-bold text-white">
                  Jobs For You
                </h2>
                <span className="px-3 py-1 bg-emerald-500/20 text-emerald-300 rounded-full text-sm font-medium">
                  {recommendations.jobs.length} items
                </span>
                {userLocation?.city && (
                  <span className="px-3 py-1 bg-white/10 text-gray-300 rounded-full text-xs font-medium">
                    {[userLocation.city, userLocation.region, userLocation.country]
                      .filter(Boolean)
                      .join(", ")}
                  </span>
                )}
              </div>
            </div>

            {jobsLoading ? (
              <div className="text-center py-8 text-gray-400">
                <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-emerald-400 mb-3"></div>
                <p>Searching jobs nearby…</p>
              </div>
            ) : jobsError ? (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
                <p className="text-red-300 text-sm">
                  Couldn't load jobs: {jobsError}
                </p>
              </div>
            ) : recommendations.jobs.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                <Briefcase className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No job recommendations yet</p>
                <p className="text-sm mt-2">
                  Sync more activity so we can match jobs to your interests.
                </p>
              </div>
            ) : (
              <div className="grid lg:grid-cols-3 gap-6">
                {recommendations.jobs.map((job, index) => (
                  <motion.div
                    key={job.id}
                    initial={{ opacity: 0, x: -30 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.6, delay: index * 0.1 }}
                  >
                    <RecommendationCard type="job" data={job} />
                  </motion.div>
                ))}
              </div>
            )}
          </motion.section>
        )}

        {/* Quick Actions */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.6 }}
          className="text-center"
        >
          <div className="flex flex-wrap justify-center gap-4">
            <GlowButton variant="primary" size="medium" onClick={() => navigate("/about")}>
            Made with 🫶 By SyncMind Team 
            </GlowButton>
          </div>
        </motion.div>
      </div>
    </div>
  )
}

export default Dashboard