/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        agent: {
          DEFAULT: '#F59E0B',
          dim: '#78490A',
          glow: 'rgba(245,158,11,0.15)'
        },
        system: {
          DEFAULT: '#3B82F6',
          dim: '#1E3A5F'
        },
        surface: {
          base: '#0A0A0A',
          raised: '#111111',
          elevated: '#1A1A1A'
        },
      },
    },
  },
  plugins: [],
}
