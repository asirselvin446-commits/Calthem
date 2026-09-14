/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "SF Pro Display",
               "Segoe UI", "Inter", "system-ui", "sans-serif"],
      },
      colors: {
        ink: {
          950: "#050506",
          900: "#0a0a0c",
          800: "#141417",
          700: "#1d1d21",
        },
      },
      borderRadius: {
        "4xl": "2rem",
      },
      boxShadow: {
        glass: "0 8px 40px -12px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.06)",
        "glass-lg": "0 24px 80px -20px rgba(0,0,0,0.7), inset 0 1px 0 rgba(255,255,255,0.08)",
      },
      backdropBlur: {
        xs: "2px",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.9)", opacity: "0.7" },
          "80%,100%": { transform: "scale(1.6)", opacity: "0" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.5s ease forwards",
        "pulse-ring": "pulse-ring 1.6s cubic-bezier(0.2,0.6,0.4,1) infinite",
      },
    },
  },
  plugins: [],
};
