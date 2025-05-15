# Chat-Bot-for-booking-slots

## Slot Booking Bot - Project Update Report

## Overview:

 The Slot Booking Bot is an automated tool designed to efficiently book slots on the Saveetha LMS platform, even in high-traffic conditions. This report details the updates, new features, and enhancements made 
to improve its performance, usability, and robustness.

### Key Updates and Enhancements:

## 1. Headless Mode Fix and Optimization

Fix: Corrected the "Run Headless" option for Chrome, Firefox, and Edge browsers.

Improvement: Added logging to confirm headless mode activation.

Benefit: Enables faster, UI-free execution with reduced resource usage.

## 2. Cross-Browser Support

Feature: Added support for Chrome, Firefox, and Edge.

Implementation: Included a GUI dropdown for browser selection with specific configurations (e.g., headless mode, proxy support).

Benefit: Increases flexibility across different browser environments.

## 3. GUI Enhancements
Day Selection: Replaced text entry with a dropdown (Combobox) listing all days of the week.

Date Picker: Added a tkcalendar-based calendar picker, supporting both selection and manual typing (e.g., "6 May 2025").

Dropdowns: Converted day, schedule, and browser fields to dropdowns for easier, error-free input.

## 4. Proxy Rotation

Feature: Introduced proxy rotation to prevent IP blocking.

Implementation: Users can input a comma-separated proxy list, cycled per booking attempt.

Benefit: Enhances reliability in high-traffic or restricted scenarios.

## 5. Multi-Slot Booking

Feature: Enabled parallel booking of multiple slots using threading.

Implementation: Users can add slots to a list via the GUI for simultaneous booking.

Benefit: Speeds up the process for users needing multiple slots.

## 6. Sound Notification
Feature: Added a sound alert for successful bookings.
 
Implementation: Uses playsound library to play a success.wav file.

Benefit: Provides instant feedback, especially in headless mode.

## 7. Improved Slot Booking Logic

Enhancement: Optimized retry mechanism and switched to CSS selectors for faster, more reliable element location.

Benefit: Boosts speed and success rate under heavy traffic.

## 8. Error Handling and User Feedback
Enhancement: Improved error handling with GUI popups and detailed logging.
    
Benefit: Offers clear, actionable feedback for troubleshooting.
    
### Technical Improvements

Speed: Reduced wait times and optimized element locators.

Reliability: Enhanced stale element handling with retries.
    
Logging: Added detailed logs for progress tracking and debugging.

### Prerequisites and Setup

## To run the bot, ensure the following:

Libraries: Install selenium, tkcalendar, and playsound via pip.

Browser Drivers: Set up ChromeDriver, GeckoDriver, and EdgeDriver (links in documentation).
    
Sound File: Include a success.wav file in the project directory.
    
Instructions: Detailed setup steps are provided in the repository.

### Summary of Benefits
Reliability: Proxy rotation and retry logic improve performance in tough conditions.
    
Speed: Faster execution through optimized logic and selectors.
    
 Usability: GUI enhancements reduce errors and improve interaction.
    
Flexibility: Cross-browser and multi-slot features meet diverse needs.
    
Feedback: Sound alerts and error messages keep users informed.

### Conclusion
   
The Slot Booking Bot is now faster, more reliable, and user-friendly, with added flexibility for various use cases. These updates make it ready for GitHub upload, supported by clear documentation and well- 
commented code.

