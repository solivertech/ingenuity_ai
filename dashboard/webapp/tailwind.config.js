/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#E1F5EE',
          100: '#9FE1CB',
          200: '#5DCAA5',
          300: '#3DC49A',
          400: '#1DB88E',
          500: '#0F8F6E',
          600: '#0F6E56',
          700: '#0A5C45',
          800: '#063D2E',
          900: '#04342C',
        },
      },
    },
  },
  plugins: [],
}
