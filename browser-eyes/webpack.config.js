const path = require('path');

module.exports = {
  mode: 'production',
  entry: {
    'content-script': './src/content-script.js',
    'background': './src/background.js'
  },
  output: {
    filename: '[name].bundle.js',
    path: path.resolve(__dirname, 'dist'),
  }
};