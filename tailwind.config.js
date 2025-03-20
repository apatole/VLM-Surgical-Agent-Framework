module.exports = {
  content: ["./web/templates/**/*.html", "./web/static/**/*.js"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
        },
        dark: {
          50: '#f7f7f7',
          100: '#e3e3e3',
          200: '#c8c8c8',
          300: '#a4a4a4',
          400: '#818181',
          500: '#666666',
          600: '#515151',
          700: '#434343',
          800: '#383838',
          900: '#1a1a1a',
        },
        success: {
          300: '#4ade80',
          400: '#22c55e',
          500: '#16a34a',
          600: '#15803d',
          700: '#166534',
          800: '#14532d',
        }
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      }
    },
  },
  plugins: [
    function({ addUtilities }) {
      const newUtilities = {
        '.scrollbar-thin': {
          scrollbarWidth: 'thin',
        },
        '.scrollbar-thumb-dark-500': {
          scrollbarColor: '#666666 #434343',
        },
        '.scrollbar-track-dark-800': {
          scrollbarColor: '#434343 #383838',
        },
      }
      addUtilities(newUtilities)
    }
  ],
}