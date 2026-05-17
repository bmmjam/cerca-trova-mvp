import type { Config } from "tailwindcss";

// Palette extracted from cerca-trova.ru — the dressing-room hero:
//   deep forest green walls, warm oak floor, cream curtains, sienna leather.
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        serif: ['"Cormorant Garamond"', '"EB Garamond"', "Georgia", "serif"],
        body: ['"EB Garamond"', '"Cormorant Garamond"', "Georgia", "serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      letterSpacing: {
        widest: ".25em",
      },
      colors: {
        // Deep forest green — the dressing-room walls
        forest: {
          50: "#e8ebe7",
          100: "#c9d1c7",
          200: "#94a294",
          300: "#677561",
          400: "#3f4d3e",
          500: "#2c3a2d",
          600: "#243029",
          700: "#1d2722",
          800: "#172019",
          900: "#0f1812",
          950: "#0a110d",
        },
        // Cream / parchment — the curtains and text on dark
        cream: {
          50: "#fbf7ed",
          100: "#f5eedb",
          200: "#ebe0c1",
          300: "#ddcca0",
          400: "#cbb37b",
          500: "#b89a5c",
          600: "#9b7f48",
          700: "#7a633a",
          800: "#594931",
          900: "#3a3022",
        },
        // Warm wood / caramel — the floor and leather
        wood: {
          DEFAULT: "#a87a4a",
          light: "#c8985f",
          dark: "#7a5532",
        },
        // Primary accent — copper-amber, used like the brand's gold-trim moments
        brass: {
          DEFAULT: "#c9a04e",
          hover: "#dbb56a",
          muted: "#8a6e36",
        },
      },
      boxShadow: {
        atelier: "0 12px 30px -12px rgba(0,0,0,0.6), 0 0 0 1px rgba(184,154,92,0.08)",
        soft: "0 1px 0 0 rgba(245,238,219,0.05) inset, 0 8px 24px -12px rgba(0,0,0,0.5)",
      },
    },
  },
  plugins: [],
};

export default config;
