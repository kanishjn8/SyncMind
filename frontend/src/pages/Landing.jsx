/* global chrome */

"use client"

import {useEffect, useState} from "react"
import { motion } from "framer-motion"
import { Link, useNavigate } from "react-router-dom"
import { Github, Youtube, BookOpen, Sparkles, Zap, Target, Network, TrendingUp, User } from "lucide-react"
import { useAppContext } from "../App"
import PlatformCard from "../components/PlatformCard"
import FeatureCard from "../components/FeatureCard"
import GlowButton from "../components/GlowButton"
import ConnectedPlatformCard from "../components/ConnectedPlatformCard"

const Landing = () => {
  const navigate = useNavigate()
  const {
    isAuthenticated,
    setIsAuthenticated,
    setUser,
    user,
    isGitHubConnected,
    setIsGitHubConnected,
    isYouTubeConnected,
    setIsYouTubeConnected,
    isCourseraConnected,
    setIsCourseraConnected,
    setPlatformData,
    platformData,
  } = useAppContext()

  // Add loading states for platform data
  const [isGitHubDataLoading, setIsGitHubDataLoading] = useState(false)
  const [isYouTubeDataLoading, setIsYouTubeDataLoading] = useState(false)
  const [isCourseraDataLoading, setIsCourseraDataLoading] = useState(false)

const SESSION_STORAGE_KEY = 'platform_connections';

const saveConnectionState = (connections) => {
  try {
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(connections));
  } catch (error) {
    console.warn('Failed to save connection state:', error);
  }
};

const loadConnectionState = () => {
  try {
    const saved = sessionStorage.getItem(SESSION_STORAGE_KEY);
    return saved ? JSON.parse(saved) : {};
  } catch (error) {
    console.warn('Failed to load connection state:', error);
    return {};
  }
};

useEffect(() => {
  const updateAuthState = async () => {
    try {
      const savedConnections = loadConnectionState();
      
      if (savedConnections.isGitHubDataLoading) {
        setIsGitHubDataLoading(true);
      }
      if (savedConnections.isYouTubeDataLoading) {
        setIsYouTubeDataLoading(true);
      }
      if (savedConnections.isCourseraDataLoading) {
        setIsCourseraDataLoading(true);
      }
      
      if (savedConnections.platformData) {
        setPlatformData(savedConnections.platformData);
      }
      
      const urlParams = new URLSearchParams(window.location.search);
      const authToken = urlParams.get('auth_token');
      
      if (authToken) {
        const claimRes = await fetch(`http://localhost:8000/auth/claim?auth_token=${authToken}`, {
          credentials: "include"
        });
        const claimData = await claimRes.json();
        
        if (claimData.success) {
          window.history.replaceState({}, '', '/');
          
         if (claimData.user.platform === "github") {
  setIsGitHubConnected(true);
  setIsAuthenticated(true);

  setUser({
    name: claimData.user.name,
    email: claimData.user.email,
  });

  saveConnectionState({
    ...savedConnections,
    github: true,
    authenticated: true,
    user: {
      name: claimData.user.name,
      email: claimData.user.email
    }
  });
} else {
            // Google
            setIsYouTubeConnected(true);
            setIsAuthenticated(true);
            setUser({
              name: claimData.user.name,
              email: claimData.user.email
            });
            // Save to session storage
            saveConnectionState({
              ...savedConnections,
              youtube: true,
              authenticated: true,
              user: {
                name: claimData.user.name,
                email: claimData.user.email
              }
            });
          }
          return; // Exit early
        }
      }
      
      // Try to get auth status from backend
      const res = await fetch("http://localhost:8000/auth/status", {
        credentials: "include"
      });
      const data = await res.json();
      console.log("Auth status:", data);

      // Use backend data if available, otherwise fall back to saved state
      let shouldSetYoutube = data.google_connected || savedConnections.youtube;
      let shouldSetGithub = data.github_connected || savedConnections.github;
      let shouldSetCoursera = savedConnections.coursera;
      let shouldSetAuth = data.authenticated || savedConnections.authenticated;

      if (shouldSetYoutube && !isYouTubeConnected) {
        setIsYouTubeConnected(true);
        
        // Try to get user data from backend, fallback to saved
        if (data.google_connected && data.google_email) {
          try {
            const userRes = await fetch(`http://localhost:8000/auth/user?email=${data.google_email}`, {
              credentials: "include"
            });
            const userData = await userRes.json();
            setUser({
              name: userData.user.name,
              email: userData.email
            });
          } catch (error) {
            // Fallback to saved user data
            if (savedConnections.user) {
              setUser(savedConnections.user);
            }
          }
        } else if (savedConnections.user) {
          setUser(savedConnections.user);
        }
      }

      if (shouldSetGithub && !isGitHubConnected) {
        setIsGitHubConnected(true);
      }

      if (shouldSetCoursera && !isCourseraConnected) {
        setIsCourseraConnected(true);
      }

      if (shouldSetAuth && !isAuthenticated) {
        setIsAuthenticated(true);
      }

      // Update saved state with current backend state if available
      if (data.google_connected || data.github_connected || savedConnections.coursera) {
        saveConnectionState({
          youtube: data.google_connected || savedConnections.youtube,
          github: data.github_connected || savedConnections.github,
          coursera: savedConnections.coursera,
          authenticated: true,
          user: user || savedConnections.user,
          platformData: savedConnections.platformData,
          isGitHubDataLoading: savedConnections.isGitHubDataLoading || false,
          isYouTubeDataLoading: savedConnections.isYouTubeDataLoading || false,
          isCourseraDataLoading: savedConnections.isCourseraDataLoading || false
        });
      }

    } catch (err) {
      console.error("Auth state check failed", err);
      
      const savedConnections = loadConnectionState();
      if (savedConnections.authenticated) {
        setIsAuthenticated(true);
        if (savedConnections.youtube) setIsYouTubeConnected(true);
        if (savedConnections.github) setIsGitHubConnected(true);
        if (savedConnections.coursera) setIsCourseraConnected(true);
        if (savedConnections.user) setUser(savedConnections.user);
        if (savedConnections.platformData) setPlatformData(savedConnections.platformData);
        if (savedConnections.isGitHubDataLoading) setIsGitHubDataLoading(true);
        if (savedConnections.isYouTubeDataLoading) setIsYouTubeDataLoading(true);
        if (savedConnections.isCourseraDataLoading) setIsCourseraDataLoading(true);
      }
    }
  };

  updateAuthState();
}, [setIsAuthenticated, setUser, setIsGitHubConnected, setIsYouTubeConnected, setIsCourseraConnected]);

useEffect(() => {
  if (isAuthenticated) {
    const connections = {
      youtube: isYouTubeConnected,
      github: isGitHubConnected,
      coursera: isCourseraConnected,
      authenticated: isAuthenticated,
      user: user,
      platformData: platformData, // Save current platform data
      isGitHubDataLoading: isGitHubDataLoading,
      isYouTubeDataLoading: isYouTubeDataLoading,
      isCourseraDataLoading: isCourseraDataLoading
    };
    saveConnectionState(connections);
  }
}, [isAuthenticated, isYouTubeConnected, isGitHubConnected, isCourseraConnected, user, platformData, isGitHubDataLoading, isYouTubeDataLoading, isCourseraDataLoading]);

const handleGoogleSignIn = async () => {
  try {
    const response = await fetch("http://localhost:8000/auth/google/login");
  
    const { auth_url } = await response.json();
    if (auth_url) {
      window.location.href = auth_url;
    }
  } catch (error) {
    console.error("OAuth login failed:", error);
  }
};

const handleGitHubSignIn = async () => {
  try {
    const response = await fetch("http://localhost:8000/auth/github");
    const { url } = await response.json();
    if (url) {
      window.location.href = url;
    }
  } catch (error) {
    console.error("OAuth login failed:", error);
  }
};

const handleConnectPlatform = (platform) => {
  switch (platform) {
    case "github":
      handleGitHubSignIn(); // OAuth flow
      break;
    case "youtube":
      handleGoogleSignIn(); // OAuth flow
      break;
    case "coursera": {
      console.log("[Coursera Connect] Starting connect flow", {
        hasUserEmail: Boolean(user?.email),
        isAuthenticated,
      });

      if (!user?.email) {
        console.warn("[Coursera Connect] No user email; aborting.");
        return;
      }

      setIsCourseraDataLoading(true);
      const currentConnections = loadConnectionState();
      saveConnectionState({
        ...currentConnections,
        isCourseraDataLoading: true,
      });

      const stopCourseraLoading = (reason) => {
        console.log("[Coursera Connect] Stopping loading state", { reason });
        setIsCourseraDataLoading(false);
        const latestConnections = loadConnectionState();
        saveConnectionState({
          ...latestConnections,
          isCourseraDataLoading: false,
        });
      };

      // Hit /recommend-coursera with a (possibly empty) history. The
      // backend has a cross-platform fallback that derives keywords
      // from GitHub + YouTube activity when the scraper found nothing,
      // so this call works whether or not the extension is installed.
      const requestRecommendations = async (courses, extractorMeta) => {
        try {
          setIsCourseraConnected(true);
          setPlatformData((prev) => {
            const newData = {
              ...prev,
              coursera: { courses, ...extractorMeta },
            };
            const conns = loadConnectionState();
            saveConnectionState({
              ...conns,
              coursera: true,
              platformData: newData,
            });
            return newData;
          });

          const historyItems = (courses || []).map((course) => {
            const parts = [course.title, course.context].filter(Boolean);
            return parts.length ? parts.join(" — ") : course.url;
          });

          console.log("[Coursera Connect] Calling /recommend-coursera", {
            email: user.email,
            courseCount: courses?.length || 0,
            via: extractorMeta.via,
          });

          const res = await fetch(
            `http://localhost:8000/recommend-coursera?email=${encodeURIComponent(user.email)}`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ history: historyItems }),
              credentials: "include",
            }
          );
          const body = await res.json();
          console.log("[Coursera Connect] Recommendation response", res.status, body);

          if (res.ok) {
            setPlatformData((prev) => {
              const newData = {
                ...prev,
                coursera: { ...prev.coursera, recommendations: body },
              };
              const conns = loadConnectionState();
              saveConnectionState({
                ...conns,
                platformData: newData,
                isCourseraDataLoading: false,
              });
              return newData;
            });
          } else {
            console.error("[Coursera Connect] Recommendation API failed", body);
          }
        } catch (err) {
          console.error("[Coursera Connect] requestRecommendations error:", err);
        } finally {
          stopCourseraLoading("recommendations-done");
        }
      };

      // ----- Extension presence detection -----------------------------
      // The landing-bridge content script announces itself with an
      // EXTENSION_PRESENT message as soon as it loads, and again on
      // demand when we PING. If we don't hear back in ~700ms we assume
      // there's no extension and use the no-extension path.

      let extensionPresent = false;
      let resolvedPath = false;
      const presenceListener = (event) => {
        if (
          event.data?.source === "coursera_extractor" &&
          event.data?.type === "EXTENSION_PRESENT"
        ) {
          extensionPresent = true;
          console.log("[Coursera Connect] Extension detected", {
            version: event.data?.version,
          });
        }
      };
      window.addEventListener("message", presenceListener);
      // Ask any installed landing-bridge content script to re-announce.
      window.postMessage(
        { source: "coursera_extractor_app", type: "PING" },
        "*"
      );

      const EXTENSION_PROBE_MS = 700;

      const proceedWithoutExtension = async () => {
        if (resolvedPath) return;
        resolvedPath = true;
        window.removeEventListener("message", presenceListener);
        console.log(
          "[Coursera Connect] No extension detected — using cross-platform fallback."
        );
        await requestRecommendations([], {
          via: "no-extension-fallback",
          page: null,
        });
      };

      const proceedWithExtension = () => {
        if (resolvedPath) return;
        resolvedPath = true;
        window.removeEventListener("message", presenceListener);

        const courseraWindow = window.open(
          "https://www.coursera.org/my-learning",
          "_blank"
        );
        if (!courseraWindow) {
          console.error("[Coursera Connect] Popup blocked.");
          stopCourseraLoading("popup-blocked");
          return;
        }

        alert(
          "We opened your Coursera 'My Learning' page in a new tab.\n\n" +
            "If you're not signed into Coursera in this browser, sign in there first — we'll pick up your courses automatically once they load."
        );

        let didReceiveExtractorMessage = false;
        const handleExtracted = async (event) => {
          if (
            event.data?.source !== "coursera_extractor" ||
            event.data?.type !== "EXTRACTED"
          ) {
            return;
          }

          const payload = event.data?.payload || {};
          if (payload.needsLogin) {
            console.warn(
              "[Coursera Connect] Extension reports login required; waiting for sign-in."
            );
            return;
          }

          didReceiveExtractorMessage = true;
          clearTimeout(extractorTimeoutId);
          window.removeEventListener("message", handleExtracted);

          await requestRecommendations(payload.courses || [], {
            via: "extension",
            page: payload.page || null,
            readyReason: payload.readyReason,
            sources: payload.sources,
          });
        };

        const extractorTimeoutId = setTimeout(async () => {
          if (didReceiveExtractorMessage) return;
          console.warn(
            "[Coursera Connect] Extension didn't deliver in time — falling back."
          );
          window.removeEventListener("message", handleExtracted);
          await requestRecommendations([], {
            via: "extension-timeout-fallback",
            page: null,
          });
        }, 60000);

        window.addEventListener("message", handleExtracted);
      };

      setTimeout(() => {
        if (extensionPresent) {
          proceedWithExtension();
        } else {
          proceedWithoutExtension();
        }
      }, EXTENSION_PROBE_MS);

      break;
    }
  }
};

useEffect(() => {
  if (isGitHubConnected && user?.email) {
    const fetchGitHubData = async () => {
      try {
        // Check if we already have GitHub data in current state or session storage
        const savedConnections = loadConnectionState();
        
        // Check current platformData first, then session storage
        if (platformData?.github || savedConnections.platformData?.github) {
          console.log("GitHub data already exists, skipping fetch");
          
          // If only in session storage, update current state
          if (!platformData?.github && savedConnections.platformData?.github) {
            setPlatformData((prev) => ({
              ...prev,
              github: savedConnections.platformData.github
            }));
          }
          
          setIsGitHubDataLoading(false);
          return;
        }

        console.log("Fetching GitHub data for the first time...");
        setIsGitHubDataLoading(true);
        
        // Update session storage with loading state
        const currentConnections = loadConnectionState();
        saveConnectionState({
          ...currentConnections,
          isGitHubDataLoading: true
        });
        
        const res = await fetch(`http://localhost:8000/get_github_data?email=${user.email}`);
        const data = await res.json();

        setPlatformData((prev) => {
          const newData = {
            ...prev,
            github: data
          };
          
          // Save to session storage
          const currentConnections = loadConnectionState();
          saveConnectionState({
            ...currentConnections,
            platformData: newData,
            isGitHubDataLoading: false
          });
          
          return newData;
        });
      } catch (err) {
        console.error("Failed to fetch GitHub data:", err);
        // Clear loading state on error
        const currentConnections = loadConnectionState();
        saveConnectionState({
          ...currentConnections,
          isGitHubDataLoading: false
        });
      } finally {
        setIsGitHubDataLoading(false);
      }
    };

    fetchGitHubData();
  }
}, [isGitHubConnected, user?.email, platformData?.github]);

useEffect(() => {
  if (isYouTubeConnected && user?.email) {
    const fetchYouTubeData = async () => {
      try {
        const savedConnections = loadConnectionState();
        
        if (platformData?.youtube || savedConnections.platformData?.youtube) {
          console.log("YouTube data already exists, skipping fetch");
          
          if (!platformData?.youtube && savedConnections.platformData?.youtube) {
            setPlatformData((prev) => ({
              ...prev,
              youtube: savedConnections.platformData.youtube
            }));
          }
          
          setIsYouTubeDataLoading(false);
          return;
        }

        console.log("Fetching YouTube data for the first time...");
        setIsYouTubeDataLoading(true);
        
        const currentConnections = loadConnectionState();
        saveConnectionState({
          ...currentConnections,
          isYouTubeDataLoading: true
        });

        const res = await fetch(`http://localhost:8000/get_youtube_data?email=${user.email}`);
        const data = await res.json();

        setPlatformData((prev) => {
          const newData = {
            ...prev,
            youtube: data,
          };
          
          // Save to session storage
          const currentConnections = loadConnectionState();
          saveConnectionState({
            ...currentConnections,
            platformData: newData,
            isYouTubeDataLoading: false
          });
          
          return newData;
        });
      } catch (err) {
        console.error("Failed to fetch YouTube data:", err);
        const currentConnections = loadConnectionState();
        saveConnectionState({
          ...currentConnections,
          isYouTubeDataLoading: false
        });
      } finally {
        setIsYouTubeDataLoading(false);
      }
    };

    fetchYouTubeData();
  }
}, [isYouTubeConnected, user?.email, platformData?.youtube]);

  const platforms = [
    {
      name: "GitHub",
      icon: Github,
      description: "Track your coding journey and discover trending repositories",
      gradient: "from-gray-600 via-gray-700 to-black",
      glowColor: "shadow-gray-500/50",
      stats: "50M+ Repos",
      isConnected: isGitHubConnected,
      platform: "github",
      isLoading: isGitHubDataLoading,
    },
    {
      name: "YouTube",
      icon: Youtube,
      description: "Analyze learning videos and get AI-curated recommendations",
      gradient: "from-red-600 via-red-700 to-red-900",
      glowColor: "shadow-red-500/50",
      stats: "2B+ Videos",
      isConnected: isYouTubeConnected,
      platform: "youtube",
      isLoading: isYouTubeDataLoading,
    },
    {
      name: "Coursera",
      icon: BookOpen,
      description: "Syncs looked up courses and recommends relevant courses (Let the sync with either github or youtube complete before trying to sync coursera)",
      gradient: "from-blue-600 via-blue-700 to-blue-900",
      glowColor: "shadow-blue-500/50",
      stats: "4K+ Courses",
      isConnected: isCourseraConnected,
      platform: "coursera",
      isLoading: isCourseraDataLoading,
    },
  ]

const features = [
  {
    title: "Smart Recommendations",
    description: "AI analyzes your learning patterns across platforms to suggest the perfect next step",
    icon: Sparkles,
    color: "from-yellow-400 to-orange-500",
  },
  {
    title: "Custom AI Recommendations",
    description: "Get highly personalized project, video, and course suggestions tailored to your unique interests",
    icon: Network, // consider importing lucide-react's `Brain` icon for a better visual fit
    color: "from-cyan-400 to-blue-500",
  },
  {
    title: "Cross-platform Sync Status",
    description: "Real-time synchronization of your progress across all connected platforms",
    icon: Zap,
    color: "from-purple-400 to-pink-500",
  },
]


  return (
    <div className="relative min-h-screen pt-20">
      {/* Hero Section */}
      <section className="relative py-20 px-6 overflow-hidden">
        <div className="container mx-auto text-center relative z-10">
          <motion.div initial={{ opacity: 0, y: 50 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}>
            <motion.h1
              className="text-6xl md:text-8xl font-bold mb-6 leading-tight"
              initial={{ scale: 0.9 }}
              animate={{ scale: 1 }}
              transition={{ duration: 1, ease: "easeOut" }}
            >
              <span className="bg-gradient-to-r from-cyan-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
                Sync Your
              </span>
              <br />
              <span className="bg-gradient-to-r from-pink-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent">
                Digital Footprint
              </span>
            </motion.h1>

            <motion.p
              className="text-xl md:text-2xl text-gray-300 mb-12 max-w-4xl mx-auto leading-relaxed"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3, duration: 0.8 }}
            >
              AI-powered learning dashboard that connects your{" "}
              <span className="text-cyan-400 font-semibold">GitHub</span>,{" "}
              <span className="text-red-400 font-semibold">YouTube</span>, and{" "}
              <span className="text-blue-400 font-semibold">Coursera</span> activity to accelerate your growth
            </motion.p>
          </motion.div>

          {!isAuthenticated && (
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.5 }}
              className="flex flex-col sm:flex-row gap-6 justify-center items-center"
            >
              <GlowButton variant="primary" size="large" className="group" onClick={handleGoogleSignIn}>
                <span className="flex items-center space-x-3">
                  <span>Continue with Google</span>
                  <motion.div
                    className="w-3 h-3 bg-white rounded-full"
                    animate={{
                      scale: [1, 1.3, 1],
                      opacity: [1, 0.7, 1],
                    }}
                    transition={{
                      duration: 2,
                      repeat: Number.POSITIVE_INFINITY,
                      ease: "easeInOut",
                    }}
                  />
                </span>
              </GlowButton>

              <GlowButton variant="secondary" size="large" onClick={handleGitHubSignIn}>
                <span className="flex items-center space-x-3">
                  <Github className="w-6 h-6" />
                  <span>Continue with GitHub</span>
                </span>
              </GlowButton>
            </motion.div>
          )}

          {/* Floating Stats */}
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.8, duration: 0.8 }}
            className="mt-16 grid grid-cols-3 gap-8 max-w-2xl mx-auto"
          >
            {[
              { number: "10K+", label: "Active Users" },
              { number: "1M+", label: "Synced Activities" },
              { number: "95%", label: "Success Rate" },
            ].map((stat, index) => (
              <motion.div
                key={stat.label}
                className="text-center"
                whileHover={{ scale: 1.05 }}
                animate={{
                  y: [0, -10, 0],
                }}
                transition={{
                  y: {
                    duration: 3,
                    repeat: Number.POSITIVE_INFINITY,
                    delay: index * 0.5,
                    ease: "easeInOut",
                  },
                }}
              >
                <div className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-cyan-400 to-purple-400 bg-clip-text text-transparent">
                  {stat.number}
                </div>
                <div className="text-gray-400 text-sm mt-1">{stat.label}</div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Platform Showcase - Show for everyone */}
      <section className="py-20 px-6 relative">
        <div className="container mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <h2 className="text-5xl md:text-6xl font-bold mb-6">
              <span className="bg-gradient-to-r from-purple-400 to-cyan-400 bg-clip-text text-transparent">
                Connect Your Universe
              </span>
            </h2>
            <p className="text-xl text-gray-300 max-w-3xl mx-auto">
              Seamlessly integrate with the platforms you already use to learn and grow
            </p>
          </motion.div>

         <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
            {platforms.map((platform, index) => (
              <motion.div
                key={platform.name}
                initial={{ opacity: 0, y: 50, rotateY: -15 }}
                whileInView={{ opacity: 1, y: 0, rotateY: 0 }}
                transition={{
                  duration: 0.8,
                  delay: index * 0.2,
                  type: "spring",
                  stiffness: 100,
                }}
              >
                {(platform.isConnected || platform.isLoading) ? (
                  <ConnectedPlatformCard {...platform} />
                ) : (
                  <PlatformCard {...platform} onConnect={() => handleConnectPlatform(platform.platform)} />
                )}
              </motion.div>
            ))}
          </div>

          {/* Analytics Button - Only show when authenticated and connected */}
          {isAuthenticated && (isGitHubConnected || isYouTubeConnected || isCourseraConnected) && (
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1, duration: 0.8 }}
              className="text-center mt-12"
            >
              <GlowButton variant="primary" size="large" onClick={() => navigate("/dashboard")} className="group">
                <span className="flex items-center space-x-3">
                  <TrendingUp className="w-6 h-6" />
                  <span>Dashboard</span>
                </span>
              </GlowButton>
            </motion.div>
          )}
        </div>
      </section>

      {/* Dynamic Features Showcase */}
      <section className="py-20 px-6 relative">
        <div className="container mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center mb-16"
          >
            <h2 className="text-5xl md:text-6xl font-bold mb-6">
              <span className="bg-gradient-to-r from-pink-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent">
                Powered by AI Intelligence
              </span>
            </h2>
            <p className="text-xl text-gray-300 max-w-3xl mx-auto">
              Advanced machine learning algorithms that understand your learning style and optimize your growth
            </p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
            {features.map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, scale: 0.8 }}
                whileInView={{ opacity: 1, scale: 1 }}
                transition={{
                  duration: 0.6,
                  delay: index * 0.2,
                  type: "spring",
                  stiffness: 120,
                }}
              >
                <FeatureCard {...feature} />
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      {!isAuthenticated && (
        <section className="py-20 px-6 relative">
          <div className="container mx-auto text-center">
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              whileInView={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.8 }}
              className="relative max-w-4xl mx-auto"
            >
              <div className="absolute inset-0 bg-gradient-to-r from-purple-600/20 to-cyan-600/20 rounded-3xl blur-xl"></div>
              <div className="relative backdrop-blur-xl bg-white/5 border border-white/10 rounded-3xl p-12">
                <h3 className="text-4xl md:text-5xl font-bold mb-6">
                  <span className="bg-gradient-to-r from-cyan-400 to-purple-400 bg-clip-text text-transparent">
                    Ready to Sync Your Journey?
                  </span>
                </h3>
                <p className="text-xl text-gray-300 mb-8 max-w-2xl mx-auto">
                  Join thousands of learners who are already optimizing their growth with AI-powered insights
                </p>
                <GlowButton variant="primary" size="large" onClick={handleGoogleSignIn}>
                  <span className="flex items-center space-x-3">
                    <Target className="w-6 h-6" />
                    <span>Start Your Journey</span>
                  </span>
                </GlowButton>
              </div>
            </motion.div>
          </div>
        </section>
      )}
    </div>
  )
}

export default Landing