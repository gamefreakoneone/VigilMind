// Background script can listen for events
chrome.runtime.onInstalled.addListener(() => {
  console.log('Parental Supervisor installed');
});

// Could add additional logic here later