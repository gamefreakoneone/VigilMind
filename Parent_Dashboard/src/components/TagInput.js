import React, { useState } from 'react';

const TagInput = ({ tags, setTags, placeholder = "Type a domain and press Enter..." }) => {
  const [inputValue, setInputValue] = useState('');

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && inputValue.trim()) {
      e.preventDefault();
      const newTag = inputValue.trim().toLowerCase();

      // Basic domain validation
      if (newTag && !tags.includes(newTag)) {
        setTags([...tags, newTag]);
        setInputValue('');
      }
    } else if (e.key === 'Backspace' && !inputValue && tags.length > 0) {
      // Remove last tag when pressing backspace with empty input
      const newTags = [...tags];
      newTags.pop();
      setTags(newTags);
    }
  };

  const removeTag = (indexToRemove) => {
    setTags(tags.filter((_, index) => index !== indexToRemove));
  };

  return (
    <div className="tag-input-container">
      {tags.map((tag, index) => (
        <div key={index} className="tag">
          <span>{tag}</span>
          <button
            type="button"
            className="tag-remove"
            onClick={() => removeTag(index)}
            aria-label={`Remove ${tag}`}
          >
            ×
          </button>
        </div>
      ))}
      <input
        type="text"
        className="tag-input"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={tags.length === 0 ? placeholder : ''}
      />
    </div>
  );
};

export default TagInput;
